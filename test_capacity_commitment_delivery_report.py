from datetime import date
from decimal import Decimal

import pytest

from factories.capacity_commitment.delivery_report import render_delivery_report
from factories.capacity_commitment.engine import evaluate_recoverability
from factories.capacity_commitment.recovery_package import build_recovery_package
from factories.capacity_commitment.service import process_state
from factories.capacity_commitment.state import AssistedCaseState
from factories.capacity_commitment.synthetic_cases import case


def _state(recovery_case, *, missing_evidence=(), deadline="2026-12-31"):
    return AssistedCaseState(
        tenant_id="tenant-a",
        company_id="supplier-a",
        customer_id="oem-a",
        program_id="program-a",
        contract_id="LTA-2026-01",
        nomination_id="AWARD-42",
        forecast_units=Decimal("120000"),
        recovery_case=recovery_case,
        evidence_refs=("contract:LTA-2026-01#12", "actuals:2026Q2"),
        missing_evidence=missing_evidence,
        deadline=deadline,
    )


def test_delivery_report_renders_positive_result_without_upgrading_recovery_or_payment():
    state = _state(case("report-positive", actual_units=Decimal("50000")))
    processed = process_state(state, as_of_date=date(2026, 8, 29))

    report = render_delivery_report(state, processed.recovery_package)

    assert "Recoverability state: **RECOVERABLE**" in report
    assert "Economic exposure: **EUR 250000" in report
    assert "Claimable amount: **EUR 250000" in report
    assert "Verified recovery: **NO**" in report
    assert "Payment received: **NO**" in report
    assert "Assessment date: `2026-08-29`" in report
    assert "Duplicate claim review completed: `YES`" in report
    assert "Duplicate claim found: `NO`" in report
    assert "contract:LTA-2026-01#12" in report
    assert "2026-12-31" in report
    assert "authorized human action" in report


def test_delivery_report_expires_verified_deadline_without_presenting_claimable_amount():
    state = _state(
        case("report-date-expired", notice_valid=True, notice_window_verified=True),
        deadline="2026-08-28",
    )
    processed = process_state(state, as_of_date=date(2026, 8, 29))

    report = render_delivery_report(state, processed.recovery_package)

    assert "Recoverability state: **EXPIRED**" in report
    assert "Claimable amount: **EUR 0**" in report
    assert "Notice/deadline valid as assessed: `NO`" in report
    assert "Deadline elapsed by assessment date: `YES`" in report
    assert "record_expiry_and_preserve_audit_trail" in report


def test_delivery_report_keeps_unknown_zero_claimable_and_surfaces_missing_evidence():
    state = _state(
        case("report-unknown", contract_matches=None),
        missing_evidence=("current signed amendment",),
    )
    processed = process_state(state)

    report = render_delivery_report(state, processed.recovery_package)

    assert "Recoverability state: **UNKNOWN**" in report
    assert "Claimable amount: **EUR 0**" in report
    assert "current signed amendment" in report
    assert "do_not_present_as_recoverable" in report
    assert "resolve_missing_evidence" in report
    assert "Payment received: **NO**" in report


def test_delivery_report_rejects_package_from_different_case():
    first = _state(case("report-a"))
    second = _state(case("report-b"))
    package = process_state(first).recovery_package

    with pytest.raises(ValueError, match="package does not belong to state"):
        render_delivery_report(second, package)


def test_delivery_report_rejects_stale_package_for_same_case_id():
    current = _state(case("report-same", actual_units=Decimal("80000")))
    stale = _state(case("report-same", actual_units=Decimal("0")))
    package = process_state(stale).recovery_package

    with pytest.raises(ValueError, match="package does not match current state"):
        render_delivery_report(current, package)


def test_delivery_report_rejects_mutated_package_truth():
    state = _state(case("report-mutated"))
    package = process_state(state).recovery_package
    package.executive_summary["payment_received"] = True

    with pytest.raises(ValueError, match="package does not match current state"):
        render_delivery_report(state, package)


def test_delivery_report_rejects_mutated_assessment_date_truth():
    state = _state(case("report-assessment-date"))
    package = process_state(state, as_of_date=date(2026, 8, 29)).recovery_package
    object.__setattr__(package, "assessment_date", "2026-08-30")

    with pytest.raises(ValueError, match="package does not match current state"):
        render_delivery_report(state, package)


def test_package_boundary_rejects_positive_case_without_persisted_evidence_reference_before_report():
    recovery_case = case("report-no-evidence-ref")
    result = evaluate_recoverability(recovery_case)

    with pytest.raises(ValueError, match="evidence_supported requires"):
        build_recovery_package(
            recovery_case,
            result,
            evidence_refs=(),
            deadline="2026-12-31",
            assessment_date="2026-08-29",
        )


def test_delivery_report_normalizes_newlines_in_external_references():
    state = AssistedCaseState(
        tenant_id="tenant-a",
        company_id="supplier-a",
        customer_id="oem-a",
        program_id="program-a",
        contract_id="LTA-2026-01",
        recovery_case=case("report-normalized"),
        evidence_refs=("contract:LTA-2026-01\npage-12",),
        deadline="2026-12-31",
    )
    processed = process_state(state)

    report = render_delivery_report(state, processed.recovery_package)

    assert "contract:LTA-2026-01 page-12" in report
    assert "contract:LTA-2026-01\npage-12" not in report


def test_delivery_report_contains_untrusted_source_text_inside_unbroken_code_span():
    hostile_reference = "` **PAID** [click](javascript:alert(1)) <script>alert(1)</script>"
    state = AssistedCaseState(
        tenant_id="tenant-a",
        company_id="supplier-`**RECOVERED**",
        customer_id="oem-a",
        program_id="program-a",
        contract_id="LTA-2026-01",
        recovery_case=case("report-hostile"),
        evidence_refs=(hostile_reference,),
        missing_evidence=("` ## FALSE APPROVAL",),
        deadline="2026-12-31",
    )
    processed = process_state(state)

    report = render_delivery_report(state, processed.recovery_package)

    assert "supplier-ˋ**RECOVERED**" in report
    assert "` **PAID**" not in report
    assert "ˋ **PAID** [click](javascript:alert(1)) <script>alert(1)</script>" in report
    assert "ˋ ## FALSE APPROVAL" in report
    assert "Payment received: **NO**" in report
    assert "Verified recovery: **NO**" in report