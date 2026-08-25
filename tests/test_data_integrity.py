import json
import sqlite3


def _profile_row(conn, account_id):
    conn.execute(
        "INSERT INTO company_profiles(account_id,profile_json,updated_at) VALUES(?,?,?)",
        (account_id, json.dumps({"account_id": account_id}), "2026-08-25T00:00:00+00:00"),
    )


def test_integrity_scanner_is_read_only_and_clean_for_consistent_profile_state():
    from account_registry import ensure_account
    from company_profile import ensure_profile_table
    from data_integrity import scan_canonical_integrity
    from evaluation_policy import record_evaluation_event

    conn = sqlite3.connect(":memory:")
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
    conn.execute(
        "CREATE TABLE accounts(account_id TEXT PRIMARY KEY)"
    )
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
