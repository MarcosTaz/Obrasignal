import hashlib
import json
from decimal import Decimal

import pytest

from factories.capacity_commitment.state import AssistedCaseState, dump_state, load_state
from factories.capacity_commitment.synthetic_cases import case


def _state() -> AssistedCaseState:
    return AssistedCaseState(
        tenant_id="tenant-a",
        company_id="supplier-a",
        customer_id="oem-a",
        program_id="program-a",
        contract_id="lta-1",
        nomination_id=None,
        forecast_units=Decimal("120000"),
        recovery_case=case("strict-schema"),
        evidence_refs=("contract:1",),
        missing_evidence=(),
        deadline="2099-12-31",
    )


def _resign(envelope: dict) -> str:
    canonical = json.dumps(
        envelope["payload"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    envelope["checksum"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def test_load_state_rejects_unknown_schema_v2_payload_fields():
    envelope = json.loads(dump_state(_state()))
    envelope["payload"]["future_semantic_state"] = "must-not-be-ignored"

    with pytest.raises(ValueError, match="state payload fields"):
        load_state(_resign(envelope), expected_tenant_id="tenant-a")


def test_load_state_rejects_missing_schema_v2_payload_fields():
    envelope = json.loads(dump_state(_state()))
    envelope["payload"].pop("missing_evidence")

    with pytest.raises(ValueError, match="state payload fields"):
        load_state(_resign(envelope), expected_tenant_id="tenant-a")
