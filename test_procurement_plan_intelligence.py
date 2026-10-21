from datetime import date

import pytest

from procurement_plan_intelligence import (
    match_plan_to_tender,
    normalize_procurement_plan,
    parse_partial_date,
    plan_read_model,
)


def base(**changes):
    row = {
        "source": "TEST_PLAN",
        "signal_type": "PROCUREMENT_PLAN",
        "external_id": "plan-123",
        "title": "Bridge rehabilitation works",
        "buyer": "City Works Authority",
        "source_reference": "PROC-2027-44",
        "published_at": "2026-08-25T00:00:00Z",
        "source_updated_at": "2026-08-25T00:30:00Z",
        "official_source": True,
    }
    row.update(changes)
    return row


@pytest.mark.parametrize(
    "value,precision",
    [("2027-05-14", "EXACT"), ("2027-05", "MONTH"), ("Q2 2027", "QUARTER"), ("2027", "YEAR"), ("EARLY_2027", "WINDOW"), (None, "UNKNOWN")],
)
def test_date_precision_is_preserved(value, precision):
    parsed = parse_partial_date(value)
    assert parsed.precision == precision
    if precision != "EXACT":
        assert parsed.exact_date is None


def test_explicit_range_and_unknown():
    ranged = parse_partial_date(precision="RANGE", start="2027-04-01", end="2027-06-30")
    assert ranged.range_start == date(2027, 4, 1)
    assert ranged.range_end == date(2027, 6, 30)
    assert parse_partial_date().precision == "UNKNOWN"


def test_quarter_never_becomes_fake_official_date():
    plan = normalize_procurement_plan(base(planned_procurement_date="Q3 2027"))
    assert plan.planned_procurement_date.precision == "QUARTER"
    assert plan.planned_procurement_date.exact_date is None
    assert plan_read_model(plan)["when"] == "Q3 2027"
    assert plan_read_model(plan)["deadline"] is None


def test_month_and_year_structured_precision():
    month = normalize_procurement_plan(base(planned_procurement_date="2027-11"))
    year = normalize_procurement_plan(base(planned_procurement_date="2028"))
    assert (month.planned_procurement_date.year, month.planned_procurement_date.month) == (2027, 11)
    assert year.planned_procurement_date.year == 2028


def test_value_is_estimated_not_award_or_contract_value():
    plan = normalize_procurement_plan(base(planned_procurement_date="Q2 2027", value="5000000", currency="EUR"))
    view = plan_read_model(plan)
    assert view["estimated_value"] == "5000000"
    assert view["value_semantics"] == "ESTIMATED"
    assert "award_value" not in view and "contract_value" not in view


def test_value_range_and_multiple_currencies():
    eur = normalize_procurement_plan(base(estimated_value_min="4000000", estimated_value_max="6000000", currency="EUR"))
    brl = normalize_procurement_plan(base(external_id="br", currency="BRL", value="900000"))
    assert str(eur.estimated_value.minimum) == "4000000"
    assert str(eur.estimated_value.maximum) == "6000000"
    assert brl.estimated_value.currency == "BRL"
    with pytest.raises(ValueError):
        normalize_procurement_plan(base(currency="EURO", value="1"))


def test_status_cancelled_deferred_updated_and_active_semantics():
    assert normalize_procurement_plan(base(plan_status="PLANNED")).is_active_future_procurement
    assert normalize_procurement_plan(base(plan_status="UPDATED")).is_active_future_procurement
    assert not normalize_procurement_plan(base(plan_status="DEFERRED")).is_active_future_procurement
    assert not normalize_procurement_plan(base(plan_status="CANCELLED")).is_active_future_procurement
    assert normalize_procurement_plan(base(plan_cancelled=True)).plan_status == "CANCELLED"


def test_plan_never_masquerades_as_live_tender_or_confirmed_contract():
    plan = normalize_procurement_plan(base(planned_procurement_date="Q2 2027", value="4000000", currency="EUR"))
    view = plan_read_model(plan)
    assert plan.is_open_tender is False
    assert view["is_open_tender"] is False
    assert view["cta"] != "Submit bid"
    assert "guaranteed" in view["uncertainty_note"]


def test_identity_determinism_and_updated_fingerprint():
    one = normalize_procurement_plan(base())
    two = normalize_procurement_plan(base())
    updated = normalize_procurement_plan(base(plan_status="UPDATED"))
    assert one.signal_id == two.signal_id
    assert one.fingerprint == two.fingerprint
    assert updated.signal_id == one.signal_id
    assert updated.fingerprint != one.fingerprint


def test_buyer_location_provenance_and_budget_semantics():
    plan = normalize_procurement_plan(base(
        buyer_id="buyer-7", place="Porto", location_kind="PROJECT", category_code="45200000",
        budget_status="INDICATIVE", plan_year="2027", procurement_method="open",
        planned_procurement_date="2027-06-01",
    ))
    assert plan.buyer_id == "buyer-7"
    assert plan.location == {"kind": "PROJECT", "label": "Porto"}
    assert plan.provenance["source_reference"] == "PROC-2027-44"
    assert plan.budget_status == "INDICATIVE"
    assert plan.budget_year == 2027
    assert plan.procedure_type == "open"
    assert plan.confidence == "MEDIUM"


def test_lineage_requires_official_reference_not_similarity():
    plan = normalize_procurement_plan(base())
    ambiguous = {"signal_type": "TENDER", "external_id": "t1", "buyer": "City Works Authority", "title": "Bridge rehabilitation works"}
    assert match_plan_to_tender(plan, ambiguous) is None
    linked = {**ambiguous, "source_reference": "PROC-2027-44"}
    relation = match_plan_to_tender(plan, linked)
    assert relation["relation"] == "PLAN_TO_TENDER"
    assert relation["confidence"] == "HIGH"


def test_forecast_is_supported_but_remains_pre_tender():
    plan = normalize_procurement_plan(base(signal_type="FORECAST", external_id="forecast-1", planned_procurement_date="2028"))
    assert plan.signal_type == "FORECAST"
    assert plan.is_open_tender is False


def test_legacy_target_date_is_future_need_not_deadline():
    plan = normalize_procurement_plan(base(target_date="2027-12-23"))
    assert plan.planned_procurement_date.exact_date == date(2027, 12, 23)
    assert plan_read_model(plan)["deadline"] is None


def test_security_bounds_and_malformed_dates():
    with pytest.raises(ValueError):
        normalize_procurement_plan(base(title="x" * 501))
    with pytest.raises(ValueError):
        normalize_procurement_plan(base(description="x" * 50001))
    with pytest.raises(ValueError):
        normalize_procurement_plan(base(planned_procurement_date="2027-99", planned_procurement_precision="EXACT"))
    with pytest.raises(ValueError):
        normalize_procurement_plan(base(signal_type="TENDER"))


def test_less_precision_does_not_create_more_precise_output():
    values = ["2027-05-14", "2027-05", "Q2 2027", "2027", "NEXT_6_MONTHS", None]
    expected = ["EXACT", "MONTH", "QUARTER", "YEAR", "WINDOW", "UNKNOWN"]
    for value, precision in zip(values, expected):
        parsed = parse_partial_date(value)
        assert parsed.precision == precision
        if precision != "EXACT":
            assert parsed.exact_date is None
