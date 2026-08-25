import json
import sqlite3
from datetime import datetime, timezone

import pytest

from opportunity_compare import compare_opportunities

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def _db(rows):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE tenders (id INTEGER PRIMARY KEY, external_id TEXT, source TEXT, title TEXT, value TEXT, currency TEXT)"
    )
    conn.executemany("INSERT INTO tenders VALUES(?,?,?,?,?,?)", rows)
    return conn


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_published_value_fails_closed_and_is_json_safe(bad):
    conn = _db(
        [
            (1, "ext-1", "TEST", "Bad money", bad, "EUR"),
            (2, "ext-2", "TEST", "Finite money", "100", "EUR"),
        ]
    )
    result = compare_opportunities(conn, {"account_id": "acct"}, [1, 2], {"now": NOW})

    assert result["values_by_opportunity"]["1"]["published_value"]["status"] == "UNKNOWN"
    json.dumps(result, allow_nan=False)
    highest = next(h for h in result["highlights"] if h["key"] == "highest_published_value")
    assert highest["opportunity_ids"] == ["2"]


def test_money_ranking_preserves_precision_above_binary_float_integer_boundary():
    conn = _db(
        [
            (1, "ext-1", "TEST", "Higher", "9007199254740993", "EUR"),
            (2, "ext-2", "TEST", "Lower", "9007199254740992", "EUR"),
        ]
    )
    result = compare_opportunities(conn, {"account_id": "acct"}, [1, 2], {"now": NOW})

    highest = next(h for h in result["highlights"] if h["key"] == "highest_published_value")
    assert highest["opportunity_ids"] == ["1"]
    assert highest["value"] == {"amount": 9007199254740993, "currency": "EUR"}


def test_fractional_money_highlight_preserves_exact_decimal_text():
    conn = _db(
        [
            (1, "ext-1", "TEST", "Higher", "100.10", "EUR"),
            (2, "ext-2", "TEST", "Lower", "100.09", "EUR"),
        ]
    )
    result = compare_opportunities(conn, {"account_id": "acct"}, [1, 2], {"now": NOW})

    highest = next(h for h in result["highlights"] if h["key"] == "highest_published_value")
    assert highest["opportunity_ids"] == ["1"]
    assert highest["value"] == {"amount": "100.10", "currency": "EUR"}


def test_negative_published_value_is_not_comparable_money():
    conn = _db(
        [
            (1, "ext-1", "TEST", "Invalid", "-1", "EUR"),
            (2, "ext-2", "TEST", "Valid", "0", "EUR"),
        ]
    )
    result = compare_opportunities(conn, {"account_id": "acct"}, [1, 2], {"now": NOW})

    assert result["values_by_opportunity"]["1"]["published_value"]["status"] == "UNKNOWN"
    highest = next(h for h in result["highlights"] if h["key"] == "highest_published_value")
    assert highest["opportunity_ids"] == ["2"]
