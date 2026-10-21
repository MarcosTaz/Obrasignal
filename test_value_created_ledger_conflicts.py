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


def record(conn, *, category, amount, causal_reference):
    return record_value_event(
        conn,
        account_id="account-a",
        category=category,
        value_type="MEASURED",
        occurred_at=NOW,
        source="SYSTEM",
        amount=amount,
        currency="EUR",
        causal_reference=causal_reference,
    )


def test_same_causal_benefit_same_amount_counts_once():
    conn = db()
    record(conn, category="mobilization_saving", amount="3000", causal_reference="benefit:1")
    record(conn, category="margin_preserved", amount="3000", causal_reference="benefit:1")

    summary = get_value_summary(conn, account_id="account-a")

    assert summary.measured_by_currency == {"EUR": Decimal("3000")}


def test_same_causal_benefit_conflicting_amounts_fail_closed():
    conn = db()
    record(conn, category="mobilization_saving", amount="3000", causal_reference="benefit:1")
    record(conn, category="margin_preserved", amount="2800", causal_reference="benefit:1")

    with pytest.raises(ValueError, match="conflicting amounts for causal_reference"):
        get_value_summary(conn, account_id="account-a")


def test_conflicting_causal_amount_can_be_resolved_append_only():
    conn = db()
    original = record(
        conn, category="mobilization_saving", amount="3000", causal_reference="benefit:1"
    )
    record(
        conn, category="margin_preserved", amount="2800", causal_reference="benefit:1"
    )
    record_value_event(
        conn,
        account_id="account-a",
        category="mobilization_saving",
        value_type="MEASURED",
        occurred_at=NOW,
        source="MANUAL_CONFIRMATION",
        amount="2800",
        currency="EUR",
        causal_reference="benefit:1",
        corrects_event_id=original.event_id,
        evidence_refs=("invoice:confirmed",),
    )

    summary = get_value_summary(conn, account_id="account-a")

    assert summary.measured_by_currency == {"EUR": Decimal("2800")}
