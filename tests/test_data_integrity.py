import json
import sqlite3
from pathlib import Path


def _profile_row(conn, account_id):
    conn.execute(
        "INSERT INTO company_profiles(account_id,profile_json,updated_at) VALUES(?,?,?)",
        (account_id, json.dumps({"account_id": account_id}), "2026-08-25T00:00:00+00:00"),
    )


def _tenders_table(conn):
    conn.execute(
        """CREATE TABLE tenders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            UNIQUE(source, external_id)
        )"""
    )


def test_integrity_scanner_is_read_only_and_clean_for_consistent_profile_state():
    from account_registry import ensure_account
    from company_profile import ensure_profile_table
    from data_integrity import scan_canonical_integrity
    from evaluation_policy import record_evaluation_event

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_account(conn, "tenant-a")
    ensure_profile_table(conn)
    _profile_row(conn, "tenant-a")
    record_evaluation_event(conn, "tenant-a", "profile_ready")
    conn.execute("PRAGMA query_only=ON")

    assert scan_canonical_integrity(conn, exact_sha="deadbeef") == []
    conn.close()


def test_integrity_scanner_detects_profile_account_orphan_without_private_id():
    from company_profile import ensure_profile_table
    from data_integrity import report_json, scan_canonical_integrity

    conn = sqlite3.connect(":memory:")
    ensure_profile_table(conn)
    conn.execute("CREATE TABLE accounts(account_id TEXT PRIMARY KEY)")
    _profile_row(conn, "private-tenant-a")
    conn.commit()

    findings = scan_canonical_integrity(conn, exact_sha="abc12345")
    assert [item.invariant for item in findings] == ["PROFILE_ACCOUNT_ORPHAN"]
    assert findings[0].severity == "HIGH"
    assert findings[0].unknown is True
    payload = report_json(findings)
    assert "private-tenant-a" not in payload
    assert "abc12345" in payload
    conn.close()


def test_integrity_scanner_detects_profile_ready_event_missing():
    from account_registry import ensure_account
    from company_profile import ensure_profile_table
    from data_integrity import scan_canonical_integrity

    conn = sqlite3.connect(":memory:")
    ensure_account(conn, "tenant-a")
    ensure_profile_table(conn)
    _profile_row(conn, "tenant-a")
    conn.commit()

    findings = scan_canonical_integrity(conn)
    matching = [item for item in findings if item.invariant == "PROFILE_READY_EVENT_MISSING"]
    assert len(matching) == 1
    assert matching[0].severity == "MEDIUM"
    assert matching[0].repairable is True
    assert matching[0].unknown is False
    conn.close()


def test_integrity_scanner_detects_profile_ready_without_profile():
    from account_registry import ensure_account
    from data_integrity import scan_canonical_integrity
    from evaluation_policy import record_evaluation_event

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_account(conn, "tenant-a")
    conn.execute(
        "CREATE TABLE company_profiles(account_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    record_evaluation_event(conn, "tenant-a", "profile_ready")

    findings = scan_canonical_integrity(conn)
    matching = [item for item in findings if item.invariant == "PROFILE_READY_WITHOUT_PROFILE"]
    assert len(matching) == 1
    assert matching[0].severity == "HIGH"
    assert matching[0].unknown is True
    conn.close()


def test_integrity_scanner_detects_tenant_orphans_across_customer_state():
    from data_integrity import scan_canonical_integrity
    from decision_log import ensure_decision_table
    from notification_events import ensure_event_table
    from opportunity_workflow import ensure_workflow_table

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE accounts(account_id TEXT PRIMARY KEY)")
    ensure_decision_table(conn)
    ensure_workflow_table(conn)
    ensure_event_table(conn)
    conn.execute(
        """INSERT INTO opportunity_decisions
           (account_id,source,external_id,decision,reason,score,features_json,rule_version,decided_at)
           VALUES('missing-a','TED','D-1','GO','reason',80,'{}','v1','2026-08-25T00:00:00+00:00')"""
    )
    conn.execute(
        """INSERT INTO opportunity_workflow(account_id,source,external_id,status,note,updated_at)
           VALUES('missing-b','TED','W-1','NEW',NULL,'2026-08-25T00:00:00+00:00')"""
    )
    conn.execute(
        """INSERT INTO opportunity_events(account_id,event_key,tender_id,source,event_type,score,created_at)
           VALUES('missing-c','missing-c:event',NULL,'TED','new_high_match',90,'2026-08-25T00:00:00+00:00')"""
    )
    conn.commit()

    invariants = {item.invariant for item in scan_canonical_integrity(conn)}
    assert "DECISION_ACCOUNT_ORPHAN" in invariants
    assert "WORKFLOW_ACCOUNT_ORPHAN" in invariants
    assert "OPPORTUNITY_EVENT_ACCOUNT_ORPHAN" in invariants
    conn.close()


def test_integrity_scanner_detects_workflow_and_decision_opportunity_orphans():
    from account_registry import ensure_account
    from data_integrity import scan_canonical_integrity
    from decision_log import ensure_decision_table
    from opportunity_workflow import ensure_workflow_table

    conn = sqlite3.connect(":memory:")
    ensure_account(conn, "tenant-a")
    _tenders_table(conn)
    ensure_decision_table(conn)
    ensure_workflow_table(conn)
    conn.execute(
        """INSERT INTO opportunity_decisions
           (account_id,source,external_id,decision,reason,score,features_json,rule_version,decided_at)
           VALUES('tenant-a','TED','missing-decision','GO','reason',80,'{}','v1','2026-08-25T00:00:00+00:00')"""
    )
    conn.execute(
        """INSERT INTO opportunity_workflow(account_id,source,external_id,status,note,updated_at)
           VALUES('tenant-a','TED','missing-workflow','NEW',NULL,'2026-08-25T00:00:00+00:00')"""
    )
    conn.commit()

    invariants = {item.invariant for item in scan_canonical_integrity(conn)}
    assert "DECISION_OPPORTUNITY_ORPHAN" in invariants
    assert "WORKFLOW_OPPORTUNITY_ORPHAN" in invariants
    conn.close()


def test_integrity_scanner_detects_event_tender_source_and_tenant_key_drift():
    from account_registry import ensure_account
    from data_integrity import scan_canonical_integrity
    from notification_events import ensure_event_table

    conn = sqlite3.connect(":memory:")
    ensure_account(conn, "tenant-a")
    _tenders_table(conn)
    ensure_event_table(conn)
    conn.execute("INSERT INTO tenders(id,source,external_id) VALUES(1,'TED','T-1')")
    conn.execute(
        """INSERT INTO opportunity_events(account_id,event_key,tender_id,source,event_type,score,created_at)
           VALUES('tenant-a','tenant-a:mismatch',1,'BASE','new_high_match',90,'2026-08-25T00:00:00+00:00')"""
    )
    conn.execute(
        """INSERT INTO opportunity_events(account_id,event_key,tender_id,source,event_type,score,created_at)
           VALUES('tenant-a','tenant-a:orphan',999,'TED','new_high_match',90,'2026-08-25T00:00:00+00:00')"""
    )
    conn.execute(
        """INSERT INTO opportunity_events(account_id,event_key,tender_id,source,event_type,score,created_at)
           VALUES('tenant-a','tenant-b:wrong-namespace',1,'TED','new_high_match',90,'2026-08-25T00:00:00+00:00')"""
    )
    conn.commit()

    invariants = {item.invariant for item in scan_canonical_integrity(conn)}
    assert "OPPORTUNITY_EVENT_TENDER_ORPHAN" in invariants
    assert "OPPORTUNITY_EVENT_SOURCE_MISMATCH" in invariants
    assert "OPPORTUNITY_EVENT_TENANT_KEY_MISMATCH" in invariants
    conn.close()


def test_integrity_manifest_preserves_canonical_prebuild_and_test_only_boundaries():
    manifest_path = Path(__file__).resolve().parents[1] / "data_integrity_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["exact_main_sha"] == "66d43f6fd51cf9cea08016dad335aaa04b711a24"
    by_fact = {entry["fact"]: entry for entry in manifest["state_families"]}
    assert by_fact["notification_device_and_delivery"]["status"] == "PREBUILD"
    assert by_fact["company_state"]["status"] == "PREBUILD"
    assert by_fact["fixture_state"]["status"] == "TEST_ONLY_NOT_CANONICAL"
    assert by_fact["saved_watchlist"]["status"] == "PREBUILD_OWNER_CONTRACT_STALE_BASE"
    assert by_fact["saved_watchlist"]["candidate"]["head_sha"].startswith("879ef882")
    assert by_fact["mobile_private_cache"]["status"] == "CANONICAL_DERIVED_RISK_OTHER_OWNER"
    assert by_fact["mobile_private_cache"]["tenant_key"] == "ABSENT_ON_CURRENT_MAIN_STORAGE_KEYS"
    account_writes = next(item for item in manifest["write_path_inventory"] if item["storage"] == "accounts")
    assert account_writes["classification"] == "SHARED_ROW_SPLIT_FACTS"
    assert account_writes["dual_truth"] is False


def test_save_profile_failure_can_leave_event_state_drift(tmp_path, monkeypatch):
    """Reproduce the canonical best-effort event seam without repairing its owner."""
    db_path = tmp_path / "integrity.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))

    import evaluation_policy

    def fail_event(*args, **kwargs):
        raise RuntimeError("synthetic event failure")

    monkeypatch.setattr(evaluation_policy, "record_evaluation_event", fail_event)

    from company_profile import save_profile
    from data_integrity import scan_canonical_integrity

    saved = save_profile({"activity": "construction"}, account_id="tenant-a")
    assert saved["account_id"] == "tenant-a"

    conn = sqlite3.connect(db_path)
    findings = scan_canonical_integrity(conn, exact_sha="66d43f6f")
    assert any(item.invariant == "PROFILE_READY_EVENT_MISSING" for item in findings)
    conn.close()
