import sqlite3
from types import SimpleNamespace

from runtime_db_hardening import _enable_wal, _optimized_account_decision_recorder


def test_wal_is_enabled_once_and_persists_for_file_database(tmp_path):
    path = tmp_path / "runtime.db"

    def db():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    app = SimpleNamespace(db=db)
    assert _enable_wal(app) == "wal"

    conn = db()
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_background_recorder_skips_unchanged_decisions_and_reuses_profile(monkeypatch):
    import account_registry
    import company_profile
    import decision_log
    import funnel_integration
    import opportunity_match_pipeline

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE sync_runs(id INTEGER PRIMARY KEY, finished_at TEXT)")
    conn.execute("INSERT INTO sync_runs VALUES(1,'2026-08-31T17:00:00+00:00')")
    conn.execute("""CREATE TABLE tenders(
        id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, last_seen TEXT
    )""")
    conn.execute("INSERT INTO tenders VALUES(1,'TED','A','2026-08-31T17:00:00+00:00')")
    conn.commit()

    profile_calls = []
    persisted = []
    evaluation = {
        "decision": "QUALIFIED",
        "reason": "same",
        "profile_score": 91,
        "lot_score": 80,
        "lot_id": "A",
        "match": True,
        "geography": {"score": 1, "reason": "ok"},
        "commercial": {},
        "economic_fit": {},
        "capability": {},
        "capability_evidence": {},
        "cpv_evidence": {},
        "hard_capability_blockers": [],
        "explanation": {},
    }

    monkeypatch.setattr(account_registry, "list_active_accounts", lambda _conn: ["tenant-a"])
    monkeypatch.setattr(company_profile, "load_profile", lambda account: profile_calls.append(account) or {"account_id": account})
    monkeypatch.setattr(opportunity_match_pipeline, "evaluate_row", lambda item, profile=None: dict(evaluation))

    original_persist = funnel_integration.persist_and_classify

    def persist(_conn, item, is_new, account_id="default", **kwargs):
        persisted.append((item["external_id"], account_id, kwargs.get("profile"), kwargs.get("evaluation")))
        decision_log.record_decision(
            _conn, item["source"], item["external_id"], evaluation["decision"],
            evaluation["reason"], score=evaluation["profile_score"],
            rule_version=opportunity_match_pipeline.RULE_VERSION,
            account_id=account_id, commit=False, ensure_schema=False,
        )
        return evaluation["decision"], evaluation["reason"]

    monkeypatch.setattr(funnel_integration, "persist_and_classify", persist)
    try:
        recorder = _optimized_account_decision_recorder(SimpleNamespace())
        assert recorder(conn) == 1
        assert recorder(conn) == 0
        assert profile_calls == ["tenant-a", "tenant-a"]
        assert len(persisted) == 1
        assert persisted[0][2] == {"account_id": "tenant-a"}
        assert persisted[0][3]["profile_score"] == 91
        assert conn.execute("SELECT COUNT(*) FROM opportunity_decisions").fetchone()[0] == 1
    finally:
        monkeypatch.setattr(funnel_integration, "persist_and_classify", original_persist)
        conn.close()
