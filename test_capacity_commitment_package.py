from decimal import Decimal

from factories.capacity_commitment.engine import RecoverabilityState, evaluate_recoverability
from factories.capacity_commitment.recovery_package import build_recovery_package
from factories.capacity_commitment.synthetic_cases import case


def test_recovery_package_preserves_positive_truth_without_fabricating_payment():
    recovery_case = case("package-positive")
    result = evaluate_recoverability(recovery_case)
    package = build_recovery_package(
        recovery_case,
        result,
        evidence_refs=("contract:12", "forecast:7", "actuals:2026Q2"),
        deadline="2026-09-30",
    )

    assert result.recoverability_state == RecoverabilityState.RECOVERABLE
    assert package.recoverability["recoverable_amount"] == Decimal("100000")
    assert package.executive_summary["verified_recovery"] is False
    assert package.executive_summary["payment_received"] is False
    assert "obtain_authorized_human_review_before_external_submission" in package.next_actions


def test_recovery_package_unknown_state_never_becomes_positive():
    recovery_case = case("package-unknown", program_matches=None)
    result = evaluate_recoverability(recovery_case)
    package = build_recovery_package(
        recovery_case,
        result,
        missing_evidence=("program_mapping",),
    )

    assert result.recoverability_state == RecoverabilityState.UNKNOWN
    assert package.recoverability["positive_position"] is False
    assert package.recoverability["claimable_amount"] == Decimal("0")
    assert "do_not_present_as_recoverable" in package.next_actions
    assert "resolve_missing_evidence" in package.next_actions


def test_recovery_package_zero_exposure_closes_without_claim_language():
    recovery_case = case("package-zero", actual_units=Decimal("100000"))
    result = evaluate_recoverability(recovery_case)
    package = build_recovery_package(recovery_case, result)

    assert result.recoverability_state == RecoverabilityState.ZERO_EXPOSURE
    assert package.recoverability["recoverable_amount"] == Decimal("0")
    assert package.next_actions == ("close_or_monitor_zero_exposure",)


def test_recovery_package_rejects_mismatched_result():
    recovery_case = case("package-a")
    other_case = case("package-b")
    result = evaluate_recoverability(other_case)

    try:
        build_recovery_package(recovery_case, result)
    except ValueError as exc:
        assert "does not belong" in str(exc)
    else:
        raise AssertionError("mismatched result must be rejected")
