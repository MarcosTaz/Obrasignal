import json
from decimal import Decimal

import pytest

from factories.capacity_commitment.engine import evaluate_recoverability
from factories.capacity_commitment.state import AssistedCaseState, dump_state, load_state
from factories.capacity_commitment.synthetic_cases import case


def make_state():
    return AssistedCaseState(
        tenant_id="tenant-a",
        company_id="supplier-1",
        customer_id="oem-1",
        program_id="program-ev-1",
        recovery_case=case("state-roundtrip"),
        evidence_refs=("contract:12", "actuals:2026Q2"),
        missing_evidence=("signed-amendment",),
        deadline="2026-09-30",
        contract_id="lta-2026-01",
        forecast_units=Decimal("120000"),
    )


def test_state_roundtrip_preserves_truth_inputs():
    original = make_state()
    serialized = dump_state(original)
    restored = load_state(serialized, expected_tenant_id="tenant-a")

    assert restored == original
    assert evaluate_recoverability(restored.recovery_case) == evaluate_recoverability(original.recovery_case)
    assert restored.forecast_units == Decimal("120000")
    assert restored.recovery_case.committed_units == Decimal("100000")
    assert restored.deadline == "2026-09-30"


def test_state_checksum_detects_mutation():
    serialized = dump_state(make_state())
    envelope = json.loads(serialized)
    envelope["payload"]["recovery_case"]["dedicated_cost"] = "999999999"
    tampered = json.dumps(envelope)

    with pytest.raises(ValueError, match="checksum mismatch"):
        load_state(tampered, expected_tenant_id="tenant-a")


def test_state_rejects_cross_tenant_restore():
    serialized = dump_state(make_state())

    with pytest.raises(PermissionError, match="tenant mismatch"):
        load_state(serialized, expected_tenant_id="tenant-b")


def test_state_rejects_missing_required_identity():
    original = make_state()
    invalid = AssistedCaseState(
        tenant_id=original.tenant_id,
        company_id="",
        customer_id=original.customer_id,
        program_id=original.program_id,
        recovery_case=original.recovery_case,
        contract_id=original.contract_id,
    )

    with pytest.raises(ValueError, match="company_id"):
        dump_state(invalid)


def test_state_requires_contract_or_nomination_anchor():
    original = make_state()
    invalid = AssistedCaseState(
        tenant_id=original.tenant_id,
        company_id=original.company_id,
        customer_id=original.customer_id,
        program_id=original.program_id,
        recovery_case=original.recovery_case,
    )

    with pytest.raises(ValueError, match="contract_id or nomination_id"):
        dump_state(invalid)


def test_state_preserves_decimal_exactness():
    original = make_state()
    custom_case = case(
        "decimal-exactness",
        dedicated_cost=Decimal("123456.7891"),
        amortization_basis_units=Decimal("30000"),
        actual_units=Decimal("12345"),
    )
    state = AssistedCaseState(
        tenant_id=original.tenant_id,
        company_id=original.company_id,
        customer_id=original.customer_id,
        program_id=original.program_id,
        recovery_case=custom_case,
        contract_id=original.contract_id,
        evidence_refs=("contract:decimal",),
        forecast_units=Decimal("34567.8901"),
        deadline="2026-10-15",
    )

    restored = load_state(dump_state(state), expected_tenant_id="tenant-a")
    assert restored.recovery_case.dedicated_cost == Decimal("123456.7891")
    assert restored.forecast_units == Decimal("34567.8901")


def test_state_rejects_negative_forecast_context():
    original = make_state()
    invalid = AssistedCaseState(
        tenant_id=original.tenant_id,
        company_id=original.company_id,
        customer_id=original.customer_id,
        program_id=original.program_id,
        recovery_case=original.recovery_case,
        contract_id=original.contract_id,
        forecast_units=Decimal("-1"),
    )

    with pytest.raises(ValueError, match="forecast_units"):
        dump_state(invalid)


def test_state_supported_evidence_requires_persisted_reference():
    original = make_state()
    invalid = AssistedCaseState(
        tenant_id=original.tenant_id,
        company_id=original.company_id,
        customer_id=original.customer_id,
        program_id=original.program_id,
        recovery_case=original.recovery_case,
        contract_id=original.contract_id,
        evidence_refs=(),
    )

    with pytest.raises(ValueError, match="evidence_supported requires"):
        dump_state(invalid)


def test_state_rejects_blank_or_duplicate_evidence_refs():
    original = make_state()
    blank = AssistedCaseState(
        tenant_id=original.tenant_id,
        company_id=original.company_id,
        customer_id=original.customer_id,
        program_id=original.program_id,
        recovery_case=original.recovery_case,
        contract_id=original.contract_id,
        evidence_refs=("contract:1", " "),
    )
    duplicate = AssistedCaseState(
        tenant_id=original.tenant_id,
        company_id=original.company_id,
        customer_id=original.customer_id,
        program_id=original.program_id,
        recovery_case=original.recovery_case,
        contract_id=original.contract_id,
        evidence_refs=("contract:1", "contract:1"),
    )

    with pytest.raises(ValueError, match="blank references"):
        dump_state(blank)
    with pytest.raises(ValueError, match="duplicate references"):
        dump_state(duplicate)


def test_state_verified_notice_window_requires_absolute_deadline():
    original = make_state()
    missing_deadline = AssistedCaseState(
        tenant_id=original.tenant_id,
        company_id=original.company_id,
        customer_id=original.customer_id,
        program_id=original.program_id,
        recovery_case=original.recovery_case,
        contract_id=original.contract_id,
        evidence_refs=original.evidence_refs,
        deadline=None,
    )

    with pytest.raises(ValueError, match="notice_window_verified requires"):
        dump_state(missing_deadline)


def test_state_rejects_noncanonical_or_impossible_deadline():
    original = make_state()
    for deadline in ("2026/09/30", "2026-02-30", " 2026-09-30"):
        invalid = AssistedCaseState(
            tenant_id=original.tenant_id,
            company_id=original.company_id,
            customer_id=original.customer_id,
            program_id=original.program_id,
            recovery_case=original.recovery_case,
            contract_id=original.contract_id,
            evidence_refs=original.evidence_refs,
            deadline=deadline,
        )
        with pytest.raises(ValueError, match="deadline"):
            dump_state(invalid)
