from datetime import date
from decimal import Decimal

import pytest

from factories.capacity_commitment.service import process_state
from factories.capacity_commitment.state import AssistedCaseState
from factories.capacity_commitment.synthetic_cases import case


def _state(recovery_case, **overrides):
    values = {
        "tenant_id": "tenant-a",
        "company_id": "supplier-a",
        "customer_id": "oem-a",
        "program_id": "program-a",
        "contract_id": "LTA-2026-01",
        "nomination_id": None,
        "forecast_units": Decimal("120000"),
        "recovery_case": recovery_case,
        "evidence_refs": ("contract:LTA-2026-01#12",),
        "missing_evidence": (),
        "deadline": "2026-12-31",
    }
    values.update(overrides)
    return AssistedCaseState(**values)


def test_process_state_rejects_missing_tenant_identity_before_package_output():
    state = _state(case("service-no-tenant"), tenant_id="")

    with pytest.raises(ValueError, match="tenant_id is required"):
        process_state(state)


def test_process_state_rejects_positive_evidence_flag_without_persisted_reference():
    state = _state(case("service-no-evidence-ref"), evidence_refs=())

    with pytest.raises(ValueError, match="evidence_supported requires"):
        process_state(state)


def test_process_state_rejects_verified_notice_window_without_persisted_deadline():
    state = _state(case("service-no-deadline"), deadline=None)

    with pytest.raises(ValueError, match="notice_window_verified requires"):
        process_state(state)


def test_process_state_expires_verified_notice_window_after_absolute_deadline():
    state = _state(
        case("service-expired-by-date", notice_valid=True, notice_window_verified=True),
        deadline="2026-08-28",
    )

    processed = process_state(state, as_of_date=date(2026, 8, 29))

    assert processed.result.recoverability_state.value == "EXPIRED"
    assert processed.result.claimable_amount == Decimal("0")
    assert processed.recovery_package.deadline == "2026-08-28"
    assert processed.recovery_package.assessment_date == "2026-08-29"
    assert processed.recovery_package.audit_trail["deadline_expired_by_date"] is True
    assert processed.recovery_package.contractual_basis["notice_valid"] is False


def test_process_state_does_not_infer_expiry_from_unverified_notice_window():
    state = _state(
        case("service-unverified-old-date", notice_valid=True, notice_window_verified=False),
        deadline="2026-08-28",
    )

    processed = process_state(state, as_of_date=date(2026, 8, 29))

    assert processed.result.recoverability_state.value == "UNKNOWN"
    assert processed.result.claimable_amount == Decimal("0")
    assert processed.recovery_package.audit_trail["deadline_expired_by_date"] is False
    assert processed.recovery_package.contractual_basis["notice_valid"] is True


def test_process_state_keeps_verified_deadline_valid_through_deadline_date():
    state = _state(
        case("service-deadline-day", notice_valid=True, notice_window_verified=True),
        deadline="2026-08-29",
    )

    processed = process_state(state, as_of_date=date(2026, 8, 29))

    assert processed.result.recoverability_state.value == "RECOVERABLE"
    assert processed.recovery_package.audit_trail["deadline_expired_by_date"] is False
