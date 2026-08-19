import sqlite3


def test_funnel_counts_use_latest_decision_per_opportunity():
    from decision_log import funnel_counts, ensure_decision_table

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)

    conn.executemany(
        """INSERT INTO opportunity_decisions
           (account_id, source, external_id, decision, reason, score, features_json, rule_version, decided_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            ("company-a", "TED", "one", "QUALIFIED", "first", 90, "{}", "commercial-v2", "2026-08-19T10:00:00+00:00"),
            ("company-a", "TED", "one", "REJECT", "latest", 40, "{}", "commercial-v2", "2026-08-19T11:00:00+00:00"),
            ("company-a", "TED", "two", "REVIEW", "latest", 65, "{}", "commercial-v2", "2026-08-19T11:00:00+00:00"),
            ("company-b", "TED", "other", "QUALIFIED", "other account", 90, "{}", "commercial-v2", "2026-08-19T11:00:00+00:00"),
        ],
    )
    conn.commit()

    assert funnel_counts(conn, "company-a") == {"REJECT": 1, "REVIEW": 1}
    conn.close()
