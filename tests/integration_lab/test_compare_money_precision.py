import sqlite3
from datetime import datetime, timezone

from opportunity_compare import compare_opportunities


def test_money_ranking_preserves_precision_above_binary_float_integer_boundary():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE tenders (id INTEGER PRIMARY KEY, external_id TEXT, source TEXT, title TEXT, value TEXT, currency TEXT)")
    conn.executemany(
        "INSERT INTO tenders VALUES(?,?,?,?,?,?)",
        [
            (1, "ext-1", "TEST", "Higher", "9007199254740993", "EUR"),
            (2, "ext-2", "TEST", "Lower", "9007199254740992", "EUR"),
        ],
    )
    result = compare_opportunities(
        conn,
        {"account_id": "acct"},
        [1, 2],
        {"now": datetime(2026, 8, 25, tzinfo=timezone.utc)},
    )
    highest = next(h for h in result["highlights"] if h["key"] == "highest_published_value")
    assert highest["opportunity_ids"] == ["1"]
