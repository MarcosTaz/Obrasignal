import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
import pytest

from value_created_ledger import (
    Confidence, ValueType, ensure_value_ledger_schema,
    get_value_event, get_value_summary, record_value_event,
)

NOW = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)


def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def rec(conn, **kw):
    base = dict(account_id="a", category="mobilization_saving", value_type="MEASURED",
                occurred_at=NOW, source="SYSTEM", amount="100", currency="EUR")
    base.update(kw)
    return record_value_event(conn, **base)


def test_measured_and_estimated_are_separate_and_method_retained():
    c=db(); rec(c, amount="1200")
    e=rec(c, value_type="ESTIMATED", amount="4300", method="mobilization_scenario_difference_v1", confidence="MEDIUM")
    s=get_value_summary(c, account_id="a")
    assert s.measured_by_currency == {"EUR": Decimal("1200")}
    assert s.estimated_by_currency == {"EUR": Decimal("4300")}
    assert e.method == "mobilization_scenario_difference_v1" and e.confidence == Confidence.MEDIUM


def test_qualified_opportunity_is_not_value_created():
    c=db(); rec(c, category="qualified_opportunity", value_type="QUALIFIED", amount="900000")
    s=get_value_summary(c, account_id="a")
    assert s.qualified_by_currency == {"EUR": Decimal("900000")}
    assert not s.measured_by_currency and not s.estimated_by_currency
    with pytest.raises(ValueError): rec(c, category="qualified_opportunity", value_type="MEASURED")


def test_unknown_monetary_value_supported():
    c=db(); e=rec(c, category="bad_bid_avoided", value_type="UNKNOWN", amount=None, currency="EUR")
    assert e.amount is None and e.value_type is ValueType.UNKNOWN
    assert get_value_summary(c, account_id="a").measured_by_currency == {}


def test_time_saved_without_monetization():
    c=db(); rec(c, category="time_saved", value_type="MEASURED", amount="3", currency=None, unit="hours")
    s=get_value_summary(c, account_id="a")
    assert s.time_saved_by_unit == {"hours": Decimal("3")}
    assert not s.measured_by_currency


def test_currency_isolation():
    c=db(); rec(c, amount="1000", currency="EUR"); rec(c, amount="1000", currency="USD")
    assert get_value_summary(c, account_id="a").measured_by_currency == {"EUR": Decimal("1000"), "USD": Decimal("1000")}


def test_estimated_to_measured_lifecycle_preserves_both():
    c=db(); est=rec(c, value_type="ESTIMATED", amount="4000", method="scenario_v1", causal_reference="mob:1")
    measured=rec(c, value_type="MEASURED", amount="3250", causal_reference="mob:1")
    s=get_value_summary(c, account_id="a")
    assert s.estimated_by_currency["EUR"] == Decimal("4000")
    assert s.measured_by_currency["EUR"] == Decimal("3250")
    assert get_value_event(c, account_id="a", event_id=est.event_id).amount == Decimal("4000")
    assert measured.event_id != est.event_id


def test_negative_actual_regret_is_allowed():
    c=db(); rec(c, value_type="ESTIMATED", amount="5000", method="prediction_v1", causal_reference="d:1")
    rec(c, value_type="MEASURED", amount="-1000", causal_reference="d:1")
    s=get_value_summary(c, account_id="a")
    assert s.estimated_by_currency["EUR"] == Decimal("5000")
    assert s.measured_by_currency["EUR"] == Decimal("-1000")


def test_account_isolation_read_and_summary():
    c=db(); e=rec(c, account_id="a", amount="10"); rec(c, account_id="b", amount="900")
    assert get_value_summary(c, account_id="a").measured_by_currency == {"EUR": Decimal("10")}
    assert get_value_event(c, account_id="b", event_id=e.event_id) is None


def test_period_filtering_and_category_breakdown():
    c=db()
    rec(c, occurred_at="2026-01-01T00:00:00+00:00", amount="1")
    rec(c, occurred_at="2026-08-01T00:00:00+00:00", category="sourcing_saving", amount="2")
    s=get_value_summary(c, account_id="a", start_at="2026-07-01T00:00:00Z", end_at="2026-08-31T23:59:59Z")
    assert s.measured_by_currency == {"EUR": Decimal("2")}
    assert s.breakdown["sourcing_saving"]["MEASURED"]["EUR"] == Decimal("2")


def test_evidence_assumptions_confidence_retained():
    c=db(); e=rec(c, evidence_refs=("ev:1","ev:2"), assumptions=("baseline invoice comparable",), confidence="HIGH")
    loaded=get_value_event(c, account_id="a", event_id=e.event_id)
    assert loaded.evidence_refs == ("ev:1","ev:2")
    assert loaded.assumptions == ("baseline invoice comparable",)
    assert loaded.confidence is Confidence.HIGH


def test_duplicate_prevention_is_tenant_scoped():
    c=db(); rec(c, deduplication_key="invoice:7")
    with pytest.raises(ValueError, match="duplicate"):
        rec(c, deduplication_key="invoice:7")
    rec(c, account_id="b", deduplication_key="invoice:7")


def test_known_causal_double_counting_is_prevented():
    c=db(); rec(c, category="mobilization_saving", amount="3000", causal_reference="benefit:x")
    rec(c, category="margin_preserved", amount="3000", causal_reference="benefit:x")
    s=get_value_summary(c, account_id="a")
    assert s.measured_by_currency == {"EUR": Decimal("3000")}


def test_correction_is_append_only_and_replaces_current_reporting():
    c=db(); old=rec(c, amount="1200")
    new=rec(c, amount="1100", corrects_event_id=old.event_id)
    assert get_value_event(c, account_id="a", event_id=old.event_id).amount == Decimal("1200")
    assert get_value_summary(c, account_id="a").measured_by_currency == {"EUR": Decimal("1100")}
    assert new.corrects_event_id == old.event_id


def test_cross_tenant_correction_rejected():
    c=db(); old=rec(c, account_id="a")
    with pytest.raises(ValueError, match="another account"):
        rec(c, account_id="b", corrects_event_id=old.event_id)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), "NaN", "Infinity"])
def test_nan_and_infinite_rejected(bad):
    c=db()
    with pytest.raises(ValueError): rec(c, amount=bad)


def test_negative_values_are_valid():
    c=db(); e=rec(c, amount="-400")
    assert e.amount == Decimal("-400")


def test_estimate_requires_method():
    c=db()
    with pytest.raises(ValueError, match="method"):
        rec(c, value_type="ESTIMATED", amount="50", method=None)


def test_schema_migration_is_idempotent():
    c=db(); ensure_value_ledger_schema(c); ensure_value_ledger_schema(c)
    indexes={r[1] for r in c.execute("PRAGMA index_list(value_events)").fetchall()}
    assert "uq_value_events_account_dedup" in indexes


def test_deterministic_summary_independent_of_insert_order_for_distinct_causes():
    c1=db(); c2=db()
    items=[dict(category="sourcing_saving", amount="2", currency="EUR", causal_reference="a"),
           dict(category="mobilization_saving", amount="3", currency="EUR", causal_reference="b")]
    for x in items: rec(c1, **x)
    for x in reversed(items): rec(c2, **x)
    assert get_value_summary(c1, account_id="a") == get_value_summary(c2, account_id="a")
