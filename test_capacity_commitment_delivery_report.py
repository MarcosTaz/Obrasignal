from decimal import Decimal

import pytest

from factories.capacity_commitment.delivery_report import render_delivery_report
from factories.capacity_commitment.service import process_state
from factories.capacity_commitment.state import AssistedCaseState
from factories.capacity_commitment.synthetic_cases import case


def _state(recovery_case, *, missing_evidence=()):
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
        deadline="2026-12-31",
    )


def test_delivery_report_renders_positive_result_without_upgrading_recovery_or_payment():
    state = _state(case("report-positive", actual_units=Decimal("50000")))
    processed = process_state(state)

    report = render_delivery_report(state, processed.recovery_package)

    assert "Recoverability state: **RECOVERABLE**" in report
    assert "Economic exposure: **EUR 250000" in report
    assert "Claimable amount: **EUR 250000" in report
    assert "Verified recovery: **NO**" in report
    assert "Payment received: **NO**" in report
    assert "contract:LTA-2026-01#12" in report
    assert "2026-12-31" in report
    assert "authorized human action" in report


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
