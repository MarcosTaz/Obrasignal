import sqlite3

from opportunity_match_pipeline import RULE_VERSION


def test_decision_refresh_prefetches_history_per_tenant(monkeypatch):
    import decision_refresh as refresh

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE sync_runs(id INTEGER PRIMARY KEY, finished_at TEXT);
        CREATE TABLE tenders(
          id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT, description TEXT,
          buyer TEXT, country TEXT, cpv TEXT, value TEXT, deadline TEXT, publication_date TEXT,
          published_at TEXT, market TEXT, last_seen TEXT
        );
        CREATE TABLE company_profiles(account_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE opportunity_decisions(
          id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT, source TEXT, external_id TEXT, decided_at TEXT, rule_version TEXT
        );
        INSERT INTO sync_runs VALUES(1,'2026-09-01T00:00:00+00:00');
        """
    )
    tenants = ["tenant-a", "tenant-b", "tenant-c"]
    for tenant in tenants:
        conn.execute(
            "INSERT INTO company_profiles VALUES(?,?,?)",
            (tenant, "{}", "2026-08-01T00:00:00+00:00"),
        )
    for index in range(60):
        external_id = f"opp-{index}"
        conn.execute(
            "INSERT INTO tenders VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                index + 1, "TEST", external_id, f"Opportunity {index}", "Works", "Buyer", "PRT",
                "4526", "100000", "2099-01-01", "2026-09-01", "2026-09-01T00:00:00+00:00",
                "PT", "2026-09-01T00:00:00+00:00",
            ),
        )
        for tenant in tenants:
            conn.execute(
                "INSERT INTO opportunity_decisions(account_id,source,external_id,decided_at,rule_version) VALUES(?,?,?,?,?)",
                (tenant, "TEST", external_id, "2026-08-02T00:00:00+00:00", RULE_VERSION),
            )
    refresh.ensure_decision_input_table(conn)
    conn.commit()

    monkeypatch.setattr(refresh, "list_active_accounts", lambda _conn: tenants)
    monkeypatch.setattr(refresh, "load_profile", lambda account: {"name": account, "countries": ["PRT"]})
    monkeypatch.setattr(
        refresh,
        "persist_and_classify",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("compatible history must not rescore")),
    )

    statements = []
    conn.set_trace_callback(statements.append)
    try:
        assert refresh.record_account_decisions(conn, commit_chunk=20) == 0
    finally:
        conn.set_trace_callback(None)

    # The old implementation issued one latest-decision SELECT per tenant per
    # observed tender. The production path must now use grouped prefetches.
    point_queries = [
        statement for statement in statements
        if "FROM opportunity_decisions" in statement
        and "source=" in statement
        and "external_id=" in statement
        and "ORDER BY id DESC LIMIT 1" in statement
    ]
    assert point_queries == []
    assert conn.execute("SELECT COUNT(*) FROM opportunity_decision_inputs").fetchone()[0] == len(tenants) * 60
    conn.close()
