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
    )


def test_state_roundtrip_preserves_truth_inputs():
    original = make_state()
    serialized = dump_state(original)
    restored = load_state(serialized, expected_tenant_id="tenant-a")

    assert restored == original
    assert evaluate_recoverability(restored.recovery_case) == evaluate_recoverability(original.recovery_case)


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
    )

    with pytest.raises(ValueError, match="company_id"):
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
    )

    restored = load_state(dump_state(state), expected_tenant_id="tenant-a")
    assert restored.recovery_case.dedicated_cost == Decimal("123456.7891")
