import hashlib
import json
from decimal import Decimal

import pytest

from factories.capacity_commitment.state import (
    AssistedCaseState,
    dump_state,
    load_state,
    recovery_case_to_payload,
)
from factories.capacity_commitment.synthetic_cases import case


def v3_state():
    return AssistedCaseState(
        tenant_id="tenant-a",
        company_id="supplier-1",
        customer_id="oem-1",
        program_id="program-1",
        period_id="2026-Q2",
        unit="parts",
        recovery_case=case("case-v3"),
        evidence_refs=("contract:1", "actuals:q2"),
        contract_id="lta-1",
        forecast_units=Decimal("110000"),
        deadline="2099-09-30",
    )


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def legacy_v3_envelope(state):
    payload = json.loads(dump_state(state))["payload"]
    payload["schema_version"] = 3
    payload.pop("fact_refs", None)
    raw = canonical(payload)
    return {"checksum": hashlib.sha256(raw.encode("utf-8")).hexdigest(), "payload": payload}


def test_state_current_roundtrip_preserves_period_and_unit():
    restored = load_state(dump_state(v3_state()), expected_tenant_id="tenant-a")
    assert restored == v3_state()
    assert restored.period_id == "2026-Q2"
    assert restored.unit == "parts"


def test_state_rejects_blank_or_noncanonical_context():
    for field, value in (("period_id", ""), ("period_id", " 2026-Q2"), ("unit", " parts ")):
        kwargs = v3_state().__dict__.copy()
        kwargs[field] = value
        with pytest.raises(ValueError, match=field):
            dump_state(AssistedCaseState(**kwargs))


def test_legacy_v2_snapshot_remains_readable_without_inventing_period_or_unit():
    original = v3_state()
    payload = {
        "schema_version": 2,
        "tenant_id": original.tenant_id,
        "company_id": original.company_id,
        "customer_id": original.customer_id,
        "program_id": original.program_id,
        "contract_id": original.contract_id,
        "nomination_id": original.nomination_id,
        "forecast_units": str(original.forecast_units),
        "recovery_case": recovery_case_to_payload(original.recovery_case),
        "evidence_refs": list(original.evidence_refs),
        "missing_evidence": list(original.missing_evidence),
        "deadline": original.deadline,
    }
    raw = canonical(payload)
    envelope = canonical(
        {"checksum": hashlib.sha256(raw.encode("utf-8")).hexdigest(), "payload": payload}
    )
    restored = load_state(envelope, expected_tenant_id="tenant-a")
    assert restored.period_id is None
    assert restored.unit is None
    assert restored.fact_refs == ()
    assert restored.recovery_case == original.recovery_case


def test_legacy_v3_snapshot_remains_readable_without_inventing_fact_refs():
    envelope = legacy_v3_envelope(v3_state())
    restored = load_state(json.dumps(envelope), expected_tenant_id="tenant-a")
    assert restored.period_id == "2026-Q2"
    assert restored.unit == "parts"
    assert restored.fact_refs == ()


def test_current_checksum_covers_period_and_unit():
    envelope = json.loads(dump_state(v3_state()))
    envelope["payload"]["period_id"] = "2026-Q3"
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_state(json.dumps(envelope), expected_tenant_id="tenant-a")


def test_v3_schema_rejects_unknown_context_field_even_with_valid_checksum():
    envelope = legacy_v3_envelope(v3_state())
    envelope["payload"]["silent_period_override"] = "2026-Q4"
    raw = canonical(envelope["payload"])
    envelope["checksum"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    with pytest.raises(ValueError, match="fields do not match schema version 3"):
        load_state(json.dumps(envelope), expected_tenant_id="tenant-a")
