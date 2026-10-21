from decimal import Decimal

import pytest

from construction_margin_intelligence import ChangeCandidate, MoneyRange, next_recovery_state


def _candidate(**overrides):
    values = {
        "account_id": "acct-a",
        "project_id": "project-1",
        "candidate_id": "change-1",
        "original_scope_ref": "scope-v1",
        "changed_scope_ref": "scope-v2",
        "evidence_refs": ("drawing-rev-04",),
    }
    values.update(overrides)
    return ChangeCandidate(**values)


def test_cost_impact_is_margin_at_risk_not_recoverable_value():
    impact = MoneyRange("eur", Decimal("4200"), Decimal("5100"))
    candidate = _candidate(
        evidence_status="SUPPORTED",
        estimated_cost_impact=impact,
    )

    assert candidate.margin_at_risk == impact
    assert candidate.entitlement_status == "UNKNOWN"
    assert candidate.proposed_recovery_value is None
    assert candidate.can_assert_recoverable_value is False
    assert candidate.realized_recovery is None


def test_recovery_value_fails_closed_without_supported_entitlement_and_valuation():
    with pytest.raises(ValueError, match="supported entitlement"):
        _candidate(
            evidence_status="SUPPORTED",
            estimated_cost_impact=MoneyRange("EUR", Decimal("1000"), Decimal("1200")),
            proposed_recovery_value=MoneyRange("EUR", Decimal("1400"), Decimal("1600")),
        )


def test_supported_recoverable_value_requires_both_authorities():
    candidate = _candidate(
        evidence_status="SUPPORTED",
        entitlement_status="SUPPORTED",
        valuation_status="SUPPORTED",
        estimated_cost_impact=MoneyRange("EUR", Decimal("1000"), Decimal("1200")),
        proposed_recovery_value=MoneyRange("EUR", Decimal("1400"), Decimal("1600")),
    )

    assert candidate.can_assert_recoverable_value is True
    assert candidate.realized_recovery is None


def test_paid_value_is_not_inferred_from_approval():
    candidate = _candidate(
        submitted_value=Decimal("1600"),
        approved_value=Decimal("1500"),
        recovery_state="APPROVED",
    )

    assert candidate.realized_recovery is None


def test_paid_state_requires_observed_payment_and_exposes_only_paid_value():
    candidate = _candidate(
        submitted_value=Decimal("1600"),
        approved_value=Decimal("1500"),
        paid_value=Decimal("1450"),
        recovery_state="PAID",
    )

    assert candidate.realized_recovery == Decimal("1450")


def test_impossible_financial_state_fails_closed():
    with pytest.raises(ValueError, match="approved value cannot exist"):
        _candidate(approved_value=Decimal("1000"))

    with pytest.raises(ValueError, match="paid value cannot exist"):
        _candidate(submitted_value=Decimal("1200"), paid_value=Decimal("1000"))


def test_recovery_lifecycle_is_monotonic_and_terminal_safe():
    assert next_recovery_state("DETECTED", "REVIEWED") == "REVIEWED"
    assert next_recovery_state("REVIEWED", "SUBMITTED") == "SUBMITTED"
    assert next_recovery_state("SUBMITTED", "APPROVED") == "APPROVED"
    assert next_recovery_state("APPROVED", "PAID") == "PAID"

    with pytest.raises(ValueError, match="illegal recovery transition"):
        next_recovery_state("PAID", "REVIEWED")

    with pytest.raises(ValueError, match="illegal recovery transition"):
        next_recovery_state("REJECTED", "SUBMITTED")


def test_tenant_and_project_identity_are_required():
    with pytest.raises(ValueError, match="account_id is required"):
        _candidate(account_id="")

    with pytest.raises(ValueError, match="project_id is required"):
        _candidate(project_id="")
