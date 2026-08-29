from datetime import datetime, timezone
import json
import sqlite3

import app
from company_profile import save_profile
from storage_recovery import (
    StorageRecoveryError,
    create_backup_artifact,
    inspect_database,
    production_cutover_guard,
    verified_restore_drill,
    verify_backup_artifact,
)


HEAD = "79dff11c865332612366aba20e1ed90fc6c4eac8"
ACCOUNT = "g8-synthetic-company-a"


def _connect(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def test_g8_verified_backup_restore_preserves_synthetic_company_state(monkeypatch, tmp_path):
    source = tmp_path / "live-synthetic.sqlite"
    monkeypatch.setenv("OBRASIGNAL_DB", str(source))
    monkeypatch.setattr(app, "DB", str(source))
    app.init_db()

    save_profile(
        {
            "name": "G8 Synthetic Contractor",
            "activity": "construction",
            "coverage_mode": "portugal",
            "countries": ["PRT"],
            "cpv_prefixes": ["452"],
            "services": ["construction"],
            "capability_tags": ["construction"],
            "min_value": 1000,
            "max_value": 500000,
        },
        account_id=ACCOUNT,
    )

    conn = app.db()
    try:
        tender_id = conn.execute(
            """INSERT INTO tenders(
                source,external_id,title,description,buyer,country,cpv,value,deadline,
                publication_date,url,score,first_seen,last_seen
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
            (
                "TED", "g8-opportunity-1", "Synthetic school refurbishment",
                "Backup/restore state proof", "Synthetic municipality", "PRT",
                "45214200", "250000 EUR", "2099-12-31", "2026-08-29",
                "https://example.invalid/g8", 88,
            ),
        ).lastrowid
        conn.execute(
            """INSERT INTO opportunity_events(
                account_id,event_key,tender_id,source,event_type,score,created_at
            ) VALUES(?,?,?,?,?,?,?)""",
            (ACCOUNT, f"{ACCOUNT}:ted:g8-opportunity-1", tender_id, "TED", "new_high_match", 88, "2026-08-29T18:00:00+00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    source_health = inspect_database(source)
    created_at = datetime(2026, 8, 29, 18, 30, tzinfo=timezone.utc)
    artifact = create_backup_artifact(
        source,
        tmp_path / "backups",
        label="g8",
        created_at=created_at,
        source_revision=HEAD,
    )

    artifact_path = tmp_path / "backups" / artifact["artifact_name"]
    manifest_path = artifact_path.with_suffix(artifact_path.suffix + ".manifest.json")
    assert artifact_path.is_file()
    assert manifest_path.is_file()
    assert artifact["source_revision"] == HEAD
    assert artifact["rpo_hours"] == 24
    assert artifact["rto_hours"] == 4
    assert artifact["retention_days"] == 30
    assert artifact["off_disk_required"] is True
    assert artifact["encrypted_at_rest_required"] is True
    assert artifact["artifact_name"].startswith("obrasignal-g8-20260829T183000Z-")

    verified = verify_backup_artifact(artifact_path, manifest_path)
    assert verified["ok"] is True
    assert verified["schema_fingerprint"] == source_health["schema_fingerprint"]

    restored = tmp_path / "restore-drill.sqlite"
    drill = verified_restore_drill(artifact_path, manifest_path, restored)
    assert drill["ok"] is True
    restored_health = inspect_database(restored)
    assert restored_health["schema_fingerprint"] == source_health["schema_fingerprint"]

    original = _connect(source)
    copy = _connect(restored)
    try:
        original_profile = original.execute(
            "SELECT * FROM company_profiles WHERE account_id=?",
            (ACCOUNT,),
        ).fetchone()
        restored_profile = copy.execute(
            "SELECT * FROM company_profiles WHERE account_id=?",
            (ACCOUNT,),
        ).fetchone()
        assert dict(restored_profile) == dict(original_profile)

        original_tender = original.execute(
            "SELECT source,external_id,title,buyer,country,cpv,value,score FROM tenders WHERE id=?",
            (tender_id,),
        ).fetchone()
        restored_tender = copy.execute(
            "SELECT source,external_id,title,buyer,country,cpv,value,score FROM tenders WHERE id=?",
            (tender_id,),
        ).fetchone()
        assert dict(restored_tender) == dict(original_tender)

        original_event = original.execute(
            "SELECT account_id,event_key,tender_id,source,event_type,score FROM opportunity_events WHERE account_id=?",
            (ACCOUNT,),
        ).fetchone()
        restored_event = copy.execute(
            "SELECT account_id,event_key,tender_id,source,event_type,score FROM opportunity_events WHERE account_id=?",
            (ACCOUNT,),
        ).fetchone()
        assert dict(restored_event) == dict(original_event)
    finally:
        original.close()
        copy.close()

    # Restore is create-only: an existing destination can never be overwritten.
    try:
        verified_restore_drill(artifact_path, manifest_path, restored)
    except StorageRecoveryError as exc:
        assert "destination already exists" in str(exc)
    else:
        raise AssertionError("restore unexpectedly overwrote an existing destination")

    # A production cutover requires explicit acknowledgement and is validation-only.
    try:
        production_cutover_guard(
            restored,
            expected_schema_fingerprint=source_health["schema_fingerprint"],
        )
    except StorageRecoveryError as exc:
        assert "explicit operator acknowledgement" in str(exc)
    else:
        raise AssertionError("production cutover guard accepted implicit cutover")

    cutover = production_cutover_guard(
        restored,
        expected_schema_fingerprint=source_health["schema_fingerprint"],
        explicit_operator_ack=True,
    )
    assert cutover == {"ok": True, "candidate_verified": True, "cutover_performed": False}


def test_g8_backup_artifact_tamper_fails_closed(monkeypatch, tmp_path):
    source = tmp_path / "tamper-source.sqlite"
    monkeypatch.setenv("OBRASIGNAL_DB", str(source))
    monkeypatch.setattr(app, "DB", str(source))
    app.init_db()

    artifact = create_backup_artifact(
        source,
        tmp_path / "backups",
        label="tamper",
        created_at=datetime(2026, 8, 29, 18, 45, tzinfo=timezone.utc),
        source_revision=HEAD,
    )
    artifact_path = tmp_path / "backups" / artifact["artifact_name"]
    manifest_path = artifact_path.with_suffix(artifact_path.suffix + ".manifest.json")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    try:
        verify_backup_artifact(artifact_path, manifest_path)
    except StorageRecoveryError as exc:
        assert "checksum mismatch" in str(exc)
    else:
        raise AssertionError("tampered backup manifest unexpectedly verified")
