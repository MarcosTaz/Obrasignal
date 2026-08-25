import json
import sqlite3
from datetime import datetime, timezone

import pytest

from opportunity_compare import ComparisonError, compare_opportunities


def _run(value):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE tenders (id INTEGER PRIMARY KEY, external_id TEXT, source TEXT, title TEXT, value TEXT, currency TEXT)")
    conn.executemany(
        "INSERT INTO tenders VALUES(?,?,?,?,?,?)",
        [(1, "ext-1", "TEST", "Bad money", value, "EUR"), (2, "ext-2", "TEST", "Finite money", "100", "EUR")],
    )
    try:
        result = compare_opportunities(conn, {"account_id": "acct"}, [1, 2], {"now": datetime(2026, 8, 25, tzinfo=timezone.utc)})
    except ComparisonError:
        return
    json.dumps(result, allow_nan=False)
    highest = [h for h in result.get("highlights", []) if h.get("key") == "highest_published_value"]
    assert not highest or "1" not in highest[0].get("opportunity_ids", [])


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_money_fails_closed(value):
    _run(value)
