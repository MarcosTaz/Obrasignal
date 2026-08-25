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


def test_measured_and_estimated_time_are_never_combined():
    conn = db()
    record_value_event(
        conn,
        account_id="a",
        category="time_saved",
        value_type="MEASURED",
        occurred_at=NOW,
        source="OBSERVATION",
        amount="2",
        unit="hours",
    )
    record_value_event(
        conn,
        account_id="a",
        category="time_saved",
        value_type="ESTIMATED",
        occurred_at=NOW,
        source="MODEL",
        amount="3",
        unit="hours",
        method="workflow_baseline_v1",
    )

    summary = get_value_summary(conn, account_id="a")

    assert summary.time_saved_by_unit == {"hours": Decimal("2")}
    assert summary.estimated_time_saved_by_unit == {"hours": Decimal("3")}
    assert summary.breakdown["time_saved"]["MEASURED"]["hours"] == Decimal("2")
    assert summary.breakdown["time_saved"]["ESTIMATED"]["hours"] == Decimal("3")


def test_measured_and_estimated_other_non_monetary_are_never_combined():
    conn = db()
    for value_type, amount, method in (
        ("MEASURED", "4", None),
        ("ESTIMATED", "6", "capacity_model_v1"),
    ):
        record_value_event(
            conn,
            account_id="a",
            category="idle_capacity_recovered",
            value_type=value_type,
            occurred_at=NOW,
            source="SYSTEM",
            amount=amount,
            unit="crew_days",
            method=method,
        )

    summary = get_value_summary(conn, account_id="a")

    assert summary.other_non_monetary == {
        "idle_capacity_recovered": {"crew_days": Decimal("4")}
    }
    assert summary.estimated_other_non_monetary == {
        "idle_capacity_recovered": {"crew_days": Decimal("6")}
    }


def test_unknown_value_cannot_smuggle_numeric_amount_into_summary():
    conn = db()
    with pytest.raises(ValueError, match="UNKNOWN value cannot carry a numeric amount"):
        record_value_event(
            conn,
            account_id="a",
            category="time_saved",
            value_type="UNKNOWN",
            occurred_at=NOW,
            source="SYSTEM",
            amount="99",
            unit="hours",
            status="OBSERVED",
        )


def test_event_cannot_mix_currency_and_non_monetary_unit():
    conn = db()
    with pytest.raises(ValueError, match="cannot mix currency"):
        record_value_event(
            conn,
            account_id="a",
            category="operational_cost_reduction",
            value_type="MEASURED",
            occurred_at=NOW,
            source="SYSTEM",
            amount="100",
            currency="EUR",
            unit="hours",
        )


def test_duplicate_event_id_is_not_misreported_as_deduplication_duplicate():
    conn = db()
    common = dict(
        account_id="a",
        category="sourcing_saving",
        value_type="MEASURED",
        occurred_at=NOW,
        source="SYSTEM",
        amount="10",
        currency="EUR",
        event_id="event-fixed",
    )
    record_value_event(conn, deduplication_key="producer:1", **common)

    with pytest.raises(ValueError, match="duplicate event_id"):
        record_value_event(conn, deduplication_key="producer:2", **common)
