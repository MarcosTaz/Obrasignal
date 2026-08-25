from datetime import date, datetime, timezone

import pytest

from contract_expiry import ExpiryPolicy, add_calendar_months, evaluate_contract_expiry, actionable_expiry_signal

NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)


def contract(**overrides):
    base = {
        "signal_type": "CONTRACT",
        "external_id": "C-1",
        "contract_id": "C-1",
        "contract_status": "ACTIVE",
        "buyer_id": "B-1",
        "supplier_id": "S-1",
        "source_reference": "official-register:C-1",
        "contract_value": 5_000_000,
        "currency": "EUR",
    }
    base.update(overrides)
    return base


def test_explicit_future_end_is_expiry_not_tender_or_future_value():
    a = evaluate_contract_expiry(contract(contract_end_date="2027-02-25"), NOW)
    assert a.status == "EXPIRING"
    assert a.end_date_basis == "OFFICIAL"
    assert a.days_to_expiry == 184
    assert a.expiry_window == "FORWARD"
    row = a.as_signal_record()
    assert row["signal_type"] == "CONTRACT_EXPIRY"
    assert row["is_open_tender"] is False
    assert row["replacement_procurement_confirmed"] is False
    assert row["prior_known_contract_value"] == 5_000_000
    assert "predicted" not in " ".join(row).lower()


def test_derived_end_uses_calendar_months_not_thirty_days():
    a = evaluate_contract_expiry(contract(contract_start_date="2027-01-31", duration_amount=1, duration_unit="months"), date(2027, 1, 1))
    assert a.current_known_end == "2027-02-28"
    assert a.end_date_basis == "DERIVED"
    assert "DERIVED_TERM_END_APPROACHING" in a.reason_codes
    assert add_calendar_months(date(2028, 1, 31), 1) == date(2028, 2, 29)
    assert add_calendar_months(date(2024, 2, 29), 12) == date(2025, 2, 28)


def test_partial_dates_are_preserved_without_fabricated_day():
    month = evaluate_contract_expiry(contract(contract_end_year=2027, contract_end_month=3), NOW)
    quarter = evaluate_contract_expiry(contract(contract_end_year=2027, contract_end_quarter=2), NOW)
    year = evaluate_contract_expiry(contract(contract_end_year=2027), NOW)
    assert (month.current_known_end, month.end_date_precision, month.status) == ("2027-03", "MONTH", "UNKNOWN")
    assert (quarter.current_known_end, quarter.end_date_precision) == ("2027-Q2", "QUARTER")
    assert (year.current_known_end, year.end_date_precision) == ("2027", "YEAR")


def test_award_date_without_contract_identity_or_duration_never_fabricates_expiry():
    with pytest.raises(ValueError, match="contract_id"):
        evaluate_contract_expiry({"signal_type": "AWARD", "external_id": "A-1", "award_date": "2026-01-01"}, NOW)


def test_unknown_and_open_ended_contracts_do_not_emit_actionable_expiry():
    for row in (contract(), contract(open_ended=True)):
        a = evaluate_contract_expiry(row, NOW)
        assert a.status == "UNKNOWN"
        assert a.current_known_end is None
        assert not actionable_expiry_signal(a)


def test_completed_terminated_and_cancelled_are_not_expiring():
    for state in ("COMPLETED", "TERMINATED", "CANCELLED"):
        a = evaluate_contract_expiry(contract(contract_status=state, contract_end_date="2027-01-01"), NOW)
        assert a.status == state
        assert not actionable_expiry_signal(a)


def test_already_expired_is_contextual_only_inside_lookback():
    recent = evaluate_contract_expiry(contract(contract_end_date="2026-08-01"), NOW)
    old = evaluate_contract_expiry(contract(contract_end_date="2025-01-01"), NOW)
    assert recent.status == "EXPIRED" and actionable_expiry_signal(recent)
    assert old.status == "EXPIRED" and not actionable_expiry_signal(old)


def test_option_not_exercised_does_not_move_current_end():
    a = evaluate_contract_expiry(contract(contract_end_date="2027-01-01", option_periods=[{"months": 12}]), NOW)
    assert a.current_known_end == "2027-01-01"
    assert a.extension_status == "OPTION_EXISTS_NOT_EXERCISED"
    assert "OPTION_EXISTS_NOT_EXERCISED" in a.reason_codes


def test_confirmed_extension_replaces_current_term_but_preserves_semantic_reason():
    old = evaluate_contract_expiry(contract(contract_end_date="2027-01-01"), NOW)
    new = evaluate_contract_expiry(contract(contract_end_date="2027-01-01", extended_to="2028-01-01", extension_confirmed=True), NOW)
    assert old.status == "EXPIRING"
    assert new.current_known_end == "2028-01-01"
    assert new.signal_id != old.signal_id
    assert "EXTENSION_CONFIRMED" in new.reason_codes
    assert new.status == "EXPIRING"


def test_multiple_amendments_use_canonical_current_extension_not_history_guessing():
    a = evaluate_contract_expiry(contract(contract_end_date="2027-01-01", extended_to="2028-06-30", extension_confirmed=True, amendments=[{"end":"2027-06-30"},{"end":"2028-06-30"}]), NOW)
    assert a.current_known_end == "2028-06-30"


def test_future_start_contract_can_signal_if_known_end_is_in_policy_horizon():
    a = evaluate_contract_expiry(contract(contract_start_date="2026-12-01", contract_end_date="2027-05-01"), NOW)
    assert a.status == "EXPIRING"


def test_same_contract_same_clock_policy_is_deterministic_and_duplicate_sources_need_canonical_id():
    p = ExpiryPolicy()
    one = evaluate_contract_expiry(contract(contract_end_date="2027-01-01", source="REGISTER"), NOW, p)
    two = evaluate_contract_expiry(contract(contract_end_date="2027-01-01", source="AWARD_NOTICE"), NOW, p)
    assert one == two
    assert one.signal_id == two.signal_id


def test_multiple_contracts_same_buyer_remain_distinct():
    one = evaluate_contract_expiry(contract(contract_id="C-1", contract_end_date="2027-01-01"), NOW)
    two = evaluate_contract_expiry(contract(contract_id="C-2", external_id="C-2", contract_end_date="2027-01-01"), NOW)
    assert one.signal_id != two.signal_id


def test_horizon_policy_is_configurable_and_too_far_is_not_actionable():
    p = ExpiryPolicy(near_term_days=30, mid_near_days=90, forward_days=180, max_future_days=365)
    assert evaluate_contract_expiry(contract(contract_end_date="2026-09-10"), NOW, p).expiry_window == "NEAR_TERM"
    assert evaluate_contract_expiry(contract(contract_end_date="2026-11-01"), NOW, p).expiry_window == "MID_NEAR"
    assert evaluate_contract_expiry(contract(contract_end_date="2027-01-01"), NOW, p).expiry_window == "FORWARD"
    far = evaluate_contract_expiry(contract(contract_end_date="2028-01-01"), NOW, p)
    assert far.status == "OUTSIDE_HORIZON" and not actionable_expiry_signal(far, p)


def test_invalid_duration_fails_closed_to_unknown_and_extreme_policy_rejected():
    a = evaluate_contract_expiry(contract(contract_start_date="2026-01-01", duration_amount=10**9, duration_unit="days"), NOW)
    assert a.status == "UNKNOWN"
    with pytest.raises(ValueError):
        ExpiryPolicy(near_term_days=180, mid_near_days=90)


def test_moving_clock_closer_cannot_increase_days_to_expiry():
    c = contract(contract_end_date="2027-01-01")
    first = evaluate_contract_expiry(c, date(2026, 8, 25))
    later = evaluate_contract_expiry(c, date(2026, 9, 25))
    assert later.days_to_expiry < first.days_to_expiry


def test_currency_source_and_context_are_preserved_without_future_value_claim():
    a = evaluate_contract_expiry(contract(contract_end_date="2027-01-01", place="Lisboa", contract_type="services"), NOW)
    assert a.currency == "EUR"
    assert a.source_ref == "official-register:C-1"
    assert a.location == "Lisboa"
    assert a.category == "services"
    assert a.prior_known_contract_value == 5_000_000
