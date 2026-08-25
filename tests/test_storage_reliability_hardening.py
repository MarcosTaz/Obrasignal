import concurrent.futures
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

import pytest

from storage_contract import (
    KNOWN_TABLE_OWNERS,
    REGISTERED_ADDITIVE_MIGRATIONS,
    RUNTIME_CONTRACTS,
    STARTUP_CONTRACTS,
    StorageContractError,
    altered_persistent_tables,
    declared_persistent_tables,
    redundant_indexes,
    tenant_owned_tables,
    verify_database,
    verify_json_integrity,
    verify_schema,
)
from storage_migration_lock import run_serialized_schema_init
from storage_recovery import (
    StorageRecoveryError,
    create_backup_artifact,
    inspect_database,
    production_cutover_guard,
    restore_database,
    verify_backup_artifact,
    verified_restore_drill,
)


def _point_app(monkeypatch, path):
    import app
    monkeypatch.setattr(app, "DB", str(path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    return app


def _init_runtime(conn):
    from signal_store import ensure_signal_records
    from source_metadata import ensure_source_metadata
    from opportunity_lifecycle import ensure_lifecycle_table
    ensure_signal_records(conn)
    ensure_source_metadata(conn)
    ensure_lifecycle_table(conn)
    conn.commit()


def test_current_main_fresh_db_matches_complete_registered_contract(monkeypatch, tmp_path):
    path = tmp_path / "fresh.db"
    app = _point_app(monkeypatch, path)
    run_serialized_schema_init(app.init_db, path)
    conn = app.db()
    try:
        _init_runtime(conn)
        verify_database(conn, include_runtime=True)
    finally:
        conn.close()


def test_repeated_startup_preserves_rows(monkeypatch, tmp_path):
    path = tmp_path / "restart.db"
    app = _point_app(monkeypatch, path)
    run_serialized_schema_init(app.init_db, path)
    conn = app.db()
    conn.execute("INSERT INTO tenders(source,external_id,title) VALUES('LAB','keep','preserve')")
    conn.commit(); conn.close()
    for _ in range(4):
        run_serialized_schema_init(app.init_db, path)
    conn = app.db()
    try:
        assert conn.execute("SELECT COUNT(*) FROM tenders WHERE source='LAB' AND external_id='keep'").fetchone()[0] == 1
        verify_schema(conn, STARTUP_CONTRACTS)
    finally:
        conn.close()


def test_concurrent_first_startup_is_serialized(monkeypatch, tmp_path):
    path = tmp_path / "concurrent-first.db"
    app = _point_app(monkeypatch, path)
    def initialize(_):
        run_serialized_schema_init(app.init_db, path)
        return True
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(initialize, range(24)))
    conn = app.db()
    try:
        verify_schema(conn, STARTUP_CONTRACTS)
    finally:
        conn.close()


def test_partial_legacy_schema_migrates_without_row_loss(monkeypatch, tmp_path):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE tenders(
      id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, external_id TEXT NOT NULL,
      title TEXT, description TEXT, buyer TEXT, country TEXT, cpv TEXT, value TEXT,
      deadline TEXT, publication_date TEXT, url TEXT, score INTEGER DEFAULT 0,
      first_seen TEXT, last_seen TEXT, UNIQUE(source,external_id));
    INSERT INTO tenders(source,external_id,title) VALUES('OLD','1','historical');
    CREATE TABLE opportunity_decisions(
      id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, external_id TEXT NOT NULL,
      decision TEXT NOT NULL, reason TEXT NOT NULL, score INTEGER, features_json TEXT NOT NULL,
      rule_version TEXT NOT NULL, decided_at TEXT NOT NULL);
    INSERT INTO opportunity_decisions(source,external_id,decision,reason,features_json,rule_version,decided_at)
      VALUES('OLD','1','GO','legacy','{}','v0','2025-01-01T00:00:00+00:00');
    """)
    conn.commit(); conn.close()
    app = _point_app(monkeypatch, path)
    run_serialized_schema_init(app.init_db, path)
    conn = app.db()
    try:
        assert conn.execute("SELECT title FROM tenders WHERE source='OLD' AND external_id='1'").fetchone()[0] == "historical"
        assert conn.execute("SELECT account_id FROM opportunity_decisions WHERE external_id='1'").fetchone()[0] == "default"
        verify_schema(conn, STARTUP_CONTRACTS)
    finally:
        conn.close()


def test_corrupt_json_diagnostic_is_data_opaque(monkeypatch, tmp_path):
    path = tmp_path / "corrupt.db"
    app = _point_app(monkeypatch, path)
    run_serialized_schema_init(app.init_db, path)
    conn = app.db()
    secret = "PRIVATE-PAYLOAD-DO-NOT-LOG"
    conn.execute("INSERT INTO company_profiles(account_id,profile_json,updated_at) VALUES(?,?,?)", ("tenant-a", "{bad:"+secret, "2026-01-01"))
    conn.commit()
    try:
        with pytest.raises(StorageContractError) as caught:
            verify_json_integrity(conn)
        text = str(caught.value)
        assert "invalid_json_rows=1" in text
        assert secret not in text
        assert "tenant-a" not in text
    finally:
        conn.close()


def test_corrupt_durable_profile_never_falls_back(monkeypatch, tmp_path):
    import company_profile
    from company_profile import CompanyProfileStorageError
    path = tmp_path / "profile.db"
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps({"name":"must-not-win"}), encoding="utf-8")
    app = _point_app(monkeypatch, path)
    run_serialized_schema_init(app.init_db, path)
    monkeypatch.setenv("OBRASIGNAL_PROFILE_FILE", str(legacy))
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO company_profiles(account_id,profile_json,updated_at) VALUES('default','[1,2]','2026-01-01')")
    conn.commit(); conn.close()
    with pytest.raises(CompanyProfileStorageError, match="persisted company profile is corrupt"):
        company_profile.load_profile("default")


def test_missing_index_and_incompatible_schema_fail_closed():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE signal_records(source TEXT, external_id TEXT)")
    with pytest.raises(StorageContractError, match="missing_columns"):
        verify_schema(conn, {"signal_records": RUNTIME_CONTRACTS["signal_records"]})
    conn.close()
    conn = sqlite3.connect(":memory:")
    from opportunity_lifecycle import ensure_lifecycle_table
    ensure_lifecycle_table(conn)
    conn.execute("DROP INDEX idx_opportunity_lifecycle_actionable")
    with pytest.raises(StorageContractError, match="missing_index"):
        verify_schema(conn, {"opportunity_lifecycle": RUNTIME_CONTRACTS["opportunity_lifecycle"]})


def test_duplicate_index_is_detected_without_row_access():
    conn = sqlite3.connect(":memory:")
    from opportunity_lifecycle import ensure_lifecycle_table
    ensure_lifecycle_table(conn)
    conn.execute("CREATE INDEX duplicate_actionable ON opportunity_lifecycle(is_actionable, source)")
    assert ("is_actionable", "source") in redundant_indexes(conn, "opportunity_lifecycle")


def test_tenant_a_workflow_cannot_be_read_or_mutated_by_tenant_b():
    from opportunity_workflow import ensure_workflow_table, get_workflow, set_workflow
    conn = sqlite3.connect(":memory:"); conn.row_factory = sqlite3.Row
    ensure_workflow_table(conn)
    set_workflow(conn, "tenant-a", "SRC", "same", "REVIEWING", "a-private")
    assert get_workflow(conn, "tenant-b", "SRC", "same")["note"] is None
    set_workflow(conn, "tenant-b", "SRC", "same", "SUBMITTED", "b-private")
    assert get_workflow(conn, "tenant-a", "SRC", "same")["note"] == "a-private"
    rows = conn.execute("SELECT account_id,status FROM opportunity_workflow WHERE source='SRC' AND external_id='same' ORDER BY account_id").fetchall()
    assert [tuple(r) for r in rows] == [("tenant-a","REVIEWING"),("tenant-b","SUBMITTED")]


def test_tenant_registry_covers_current_private_owners():
    assert tenant_owned_tables() == {
        "accounts":"account_id",
        "company_profiles":"account_id",
        "opportunity_decisions":"account_id",
        "opportunity_events":"account_id",
        "opportunity_workflow":"account_id",
        "evaluation_events":"account_id",
    }


def test_root_persistence_owners_and_alters_must_be_registered():
    root = Path(__file__).resolve().parents[1]
    declared, altered = set(), set()
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        declared.update(declared_persistent_tables(text))
        altered.update(altered_persistent_tables(text))
    assert declared <= set(KNOWN_TABLE_OWNERS)
    assert altered <= set(REGISTERED_ADDITIVE_MIGRATIONS)


def _synthetic_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE state(account_id TEXT NOT NULL, body TEXT NOT NULL)")
    conn.execute("INSERT INTO state VALUES('tenant-a','private-body')")
    conn.commit(); conn.close()


def test_deterministic_verified_backup_artifact_and_restore_drill(tmp_path):
    source = tmp_path / "source.db"; _synthetic_db(source)
    created = datetime(2026,8,25,12,0,0,tzinfo=timezone.utc)
    result = create_backup_artifact(source, tmp_path / "offdisk-staging", label="hourly", created_at=created, source_revision="deadbeef")
    assert result["artifact_name"].startswith("obrasignal-hourly-20260825T120000Z-")
    assert result["off_disk_required"] is True
    assert result["encrypted_at_rest_required"] is True
    assert result["retention_days"] > 0 and result["rpo_hours"] > 0 and result["rto_hours"] > 0
    verified = verify_backup_artifact(result["artifact"], result["manifest"])
    restored = tmp_path / "restored.db"
    drill = verified_restore_drill(result["artifact"], result["manifest"], restored)
    assert drill["schema_fingerprint"] == verified["schema_fingerprint"]
    conn = sqlite3.connect(restored)
    try:
        assert conn.execute("SELECT body FROM state").fetchone()[0] == "private-body"
    finally:
        conn.close()


def test_manifest_or_artifact_tamper_fails_restore(tmp_path):
    source = tmp_path / "source.db"; _synthetic_db(source)
    result = create_backup_artifact(source, tmp_path / "backup")
    manifest = Path(result["manifest"])
    data = json.loads(manifest.read_text(encoding="utf-8")); data["artifact_sha256"] = "0" * 64
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(StorageRecoveryError, match="checksum mismatch"):
        verify_backup_artifact(result["artifact"], manifest)
    assert not (tmp_path / "should-not-exist.db").exists()


def test_restore_and_cutover_are_create_only_and_ack_guarded(tmp_path):
    source = tmp_path / "source.db"; _synthetic_db(source)
    result = create_backup_artifact(source, tmp_path / "backup")
    candidate = tmp_path / "candidate.db"
    verified_restore_drill(result["artifact"], result["manifest"], candidate)
    with pytest.raises(StorageRecoveryError, match="explicit operator acknowledgement"):
        production_cutover_guard(candidate, expected_schema_fingerprint=result["schema_fingerprint"])
    guard = production_cutover_guard(candidate, expected_schema_fingerprint=result["schema_fingerprint"], explicit_operator_ack=True)
    assert guard == {"ok":True,"candidate_verified":True,"cutover_performed":False}
    authoritative = tmp_path / "authoritative.db"; _synthetic_db(authoritative)
    with pytest.raises(StorageRecoveryError, match="destination already exists"):
        restore_database(result["artifact"], authoritative)
    assert inspect_database(authoritative)["ok"] is True
