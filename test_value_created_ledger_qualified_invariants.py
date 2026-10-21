import sqlite3
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from value_created_ledger import get_value_summary, record_value_event

NOW = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)


def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_qualified_opportunity_requires_monetary_amount():
    conn = db()
    with pytest.raises(ValueError, match="monetary amount with currency"):
        record_value_event(
            conn,
            account_id="a",
            category="qualified_opportunity",
            value_type="QUALIFIED",
            occurred_at=NOW,
            source="SYSTEM",
            amount="10",
            unit="hours",
        )


def test_qualified_opportunity_requires_amount_when_currency_present():
    conn = db()
    with pytest.raises(ValueError, match="monetary event requires amount"):
        record_value_event(
            conn,
            account_id="a",
            category="qualified_opportunity",
            value_type="QUALIFIED",
            occurred_at=NOW,
            source="SYSTEM",
            amount=None,
            currency="EUR",
        )


def test_valid_qualified_opportunity_remains_separate_from_value_created():
    conn = db()
    record_value_event(
        conn,
        account_id="a",
        category="qualified_opportunity",
        value_type="QUALIFIED",
        occurred_at=NOW,
        source="SYSTEM",
        amount="900000",
        currency="EUR",
    )

    summary = get_value_summary(conn, account_id="a")

    assert summary.qualified_by_currency == {"EUR": Decimal("900000")}
    assert summary.measured_by_currency == {}
    assert summary.estimated_by_currency == {}
