"""Adversarial integration checks for Opportunity Compare monetary semantics.

These tests belong to the temporary integration lab, not to the canonical
capability implementation. They enforce the Parallel Engineering Standard:
non-finite money must fail closed and comparisons must not lose integer/decimal
precision through binary floating-point coercion.
"""
import json
import sqlite3
from datetime import datetime, timezone

import pytest

from opportunity_compare import ComparisonError, compare_opportunities

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE tenders (
            id INTEGER PRIMARY KEY,
            external_id TEXT,
            source TEXT,
            title TEXT,
            value TEXT,
            currency TEXT
        )"""
    )
    return conn


def _add(conn, ident, value, currency="EUR"):
    conn.execute(
        "INSERT INTO tenders(id, external_id, source, title, value, currency) VALUES(?,?,?,?,?,?)",
        (ident, f"ext-{ident}", "TEST", f"Opportunity {ident}", value, currency),
    )
    conn.commit()


def _compare(conn):
    return compare_opportunities(
        conn,
        {"account_id": "acct-integration"},
        [1, 2],
        {"now": NOW},
    )


@pytest.mark.parametrize("non_finite", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_money_fails_closed_and_never_leaks_invalid_json(non_finite):
    conn = _db()
    _add(conn, 1, non_finite)
    _add(conn, 2, "100")

    try:
        result = _compare(conn)
    except ComparisonError:
        return  # Explicit input rejection is valid fail-closed behavior.

    # If the capability degrades the bad amount instead of rejecting the
    # request, the public result must still contain only standards-compliant
    # finite JSON values. Python's allow_nan=False detects NaN/Infinity leaks.
    json.dumps(result, allow_nan=False)

    highest = [h for h in result.get("highlights", []) if h.get("key") == "highest_published_value"]
    assert not highest or "1" not in highest[0].get("opportunity_ids", [])


def test_high_value_comparison_preserves_precision_above_float_integer_boundary():
    conn = _db()
    _add(conn, 1, "9007199254740993")
    _add(conn, 2, "9007199254740992")

    result = _compare(conn)
    highest = next(h for h in result["highlights"] if h["key"] == "highest_published_value")

    # 2**53+1 and 2**53 collapse to the same binary float. A monetary
    # comparison must therefore use Decimal/integer-safe semantics instead.
    assert highest["opportunity_ids"] == ["1"]
