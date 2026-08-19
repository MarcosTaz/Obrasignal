import sqlite3

from notification_events import ensure_event_table, record_new_opportunities


def test_notification_events_are_scoped_to_account():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE tenders(id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT, buyer TEXT, deadline TEXT, country TEXT, first_seen TEXT, score INTEGER, url TEXT)")
    conn.execute(
        "INSERT INTO tenders(source, external_id, title, buyer, deadline, country, first_seen, score, url) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?, ?)",
        ("TEST", "1", "Estrutura metálica", "Buyer", "2099-01-01", "PRT", 90, "https://example.test/1"),
    )
    ensure_event_table(conn)

    a = record_new_opportunities(conn, account_id="account-a", min_score=75)
    b = record_new_opportunities(conn, account_id="account-b", min_score=75)

    assert len(a) == 1
    assert len(b) == 1
    rows = conn.execute("SELECT account_id FROM opportunity_events ORDER BY account_id").fetchall()
    assert [row["account_id"] for row in rows] == ["account-a", "account-b"]
