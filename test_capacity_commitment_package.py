from decimal import Decimal

from factories.capacity_commitment.engine import RecoverabilityState, evaluate_recoverability
from factories.capacity_commitment.recovery_package import build_recovery_package
from factories.capacity_commitment.synthetic_cases import case


EVIDENCE = ("contract:12",)
DEADLINE = "2099-12-31"
ASSESSMENT_DATE = "2026-08-29"


def test_recovery_package_preserves_positive_truth_without_fabricating_payment():
    recovery_case = case("package-positive")
    result = evaluate_recoverability(recovery_case)
    package = build_recovery_package(
        recovery_case,
        result,
        evidence_refs=("contract:12", "forecast:7", "actuals:2026Q2"),
        deadline="2099-09-30",
        assessment_date=ASSESSMENT_DATE,
    )

    assert result.recoverability_state == RecoverabilityState.RECOVERABLE
    assert package.recoverability["recoverable_amount"] == Decimal("100000")
    assert package.executive_summary["verified_recovery"] is False
    assert package.executive_summary["payment_received"] is False
    assert package.commitment_baseline["customer_matches"] is True
    assert package.commitment_baseline["contract_matches"] is True
    assert package.commitment_baseline["amendment_matches"] is True
    assert package.dedicated_capacity["asset_dedication_verified"] is True
    assert package.mitigation["mitigation_reviewed"] is True
    assert package.mitigation["prior_recovery_reviewed"] is True
    assert package.contractual_basis["notice_window_verified"] is True
    assert package.contractual_basis["duplicate_claim_reviewed"] is True
    assert package.audit_trail["deadline"] == "2099-09-30"
    assert package.audit_trail["assessment_date"] == ASSESSMENT_DATE
    assert package.audit_trail["engine_version"] == result.engine_version
    assert "obtain_authorized_human_review_before_external_submission" in package.next_actions


def test_recovery_package_unknown_state_never_becomes_positive():
    recovery_case = case("package-unknown", contract_matches=False)
    result = evaluate_recoverability(recovery_case)
    package = build_recovery_package(
        recovery_case,
        result,
        evidence_refs=EVIDENCE,
        missing_evidence=("contract_mapping",),
        deadline=DEADLINE,
        assessment_date=ASSESSMENT_DATE,
    )

    assert result.recoverability_state == RecoverabilityState.UNKNOWN
    assert package.recoverability["positive_position"] is False
    assert package.recoverability["claimable_amount"] == Decimal("0")
    assert package.contractual_basis["contract_matches"] is False
    assert "do_not_present_as_recoverable" in package.next_actions
    assert "resolve_missing_evidence" in package.next_actions


def test_recovery_package_unreviewed_mitigation_is_visible_and_zero_claimable():
    recovery_case = case("package-mitigation-unknown", mitigation_reviewed=False)
    result = evaluate_recoverability(recovery_case)
    package = build_recovery_package(
        recovery_case,
        result,
        evidence_refs=EVIDENCE,
        deadline=DEADLINE,
        assessment_date=ASSESSMENT_DATE,
    )

    assert result.recoverability_state == RecoverabilityState.UNKNOWN
    assert package.mitigation["mitigation_reviewed"] is False
    assert package.recoverability["claimable_amount"] == Decimal("0")
    assert package.audit_trail["mitigation_reviewed"] is False


def test_recovery_package_zero_exposure_closes_without_claim_language():
    recovery_case = case("package-zero", actual_units=Decimal("100000"))
    result = evaluate_recoverability(recovery_case)
    package = build_recovery_package(
        recovery_case,
        result,
        evidence_refs=EVIDENCE,
        deadline=DEADLINE,
        assessment_date=ASSESSMENT_DATE,
    )

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


def test_recovery_package_rejects_stale_result_with_same_case_id():
    current_case = case("package-same-id", actual_units=Decimal("80000"))
    stale_case = case("package-same-id", actual_units=Decimal("0"))
    stale_result = evaluate_recoverability(stale_case)

    try:
        build_recovery_package(current_case, stale_result)
    except ValueError as exc:
        assert "does not match current case evaluation" in str(exc)
    else:
        raise AssertionError("same-id stale result must be rejected")