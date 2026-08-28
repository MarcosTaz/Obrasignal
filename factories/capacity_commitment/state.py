from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Optional, Tuple

from .engine import CommitmentState, CostRecoveryMode, ExposureType, RecoveryCase


SCHEMA_VERSION = 2


@dataclass(frozen=True)
class AssistedCaseState:
    tenant_id: str
    company_id: str
    customer_id: str
    program_id: str
    recovery_case: RecoveryCase
    evidence_refs: Tuple[str, ...] = ()
    missing_evidence: Tuple[str, ...] = ()
    deadline: Optional[str] = None
    contract_id: Optional[str] = None
    nomination_id: Optional[str] = None
    forecast_units: Optional[Decimal] = None


def _validate_identifier(name: str, value: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{name} is required")


def _validate_contract_anchor(contract_id: Optional[str], nomination_id: Optional[str]) -> None:
    contract = (contract_id or "").strip()
    nomination = (nomination_id or "").strip()
    if not contract and not nomination:
        raise ValueError("contract_id or nomination_id is required")


def recovery_case_to_payload(recovery_case: RecoveryCase) -> dict:
    raw = asdict(recovery_case)
    for key in (
        "committed_units",
        "actual_units",
        "dedicated_cost",
        "amortization_basis_units",
        "mitigation",
        "prior_payment",
    ):
        raw[key] = str(raw[key])
    raw["commitment_state"] = recovery_case.commitment_state.value
    raw["exposure_type"] = recovery_case.exposure_type.value
    raw["cost_recovery_mode"] = recovery_case.cost_recovery_mode.value
    return raw


def recovery_case_from_payload(raw: dict) -> RecoveryCase:
    if not isinstance(raw, dict):
        raise ValueError("recovery_case must be an object")
    required = {
        "case_id",
        "currency",
        "committed_units",
        "actual_units",
        "dedicated_cost",
        "amortization_basis_units",
        "commitment_state",
        "exposure_type",
        "cost_recovery_mode",
    }
    missing = required - set(raw)
    if missing:
        raise ValueError(f"state missing case fields: {sorted(missing)}")

    allowed = set(RecoveryCase.__dataclass_fields__)
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"unknown recovery_case fields: {sorted(unknown)}")

    values = dict(raw)
    for key in (
        "committed_units",
        "actual_units",
        "dedicated_cost",
        "amortization_basis_units",
        "mitigation",
        "prior_payment",
    ):
        if key not in values:
            values[key] = "0"
        values[key] = Decimal(str(values[key]))
    values["commitment_state"] = CommitmentState(values["commitment_state"])
    values["exposure_type"] = ExposureType(values["exposure_type"])
    values["cost_recovery_mode"] = CostRecoveryMode(values["cost_recovery_mode"])
    return RecoveryCase(**values)


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def dump_state(state: AssistedCaseState) -> str:
    for name in ("tenant_id", "company_id", "customer_id", "program_id"):
        _validate_identifier(name, getattr(state, name))
    _validate_contract_anchor(state.contract_id, state.nomination_id)
    if state.forecast_units is not None and state.forecast_units < Decimal("0"):
        raise ValueError("forecast_units must be non-negative")
    if not all(isinstance(item, str) for item in state.evidence_refs):
        raise ValueError("evidence_refs must contain strings")
    if not all(isinstance(item, str) for item in state.missing_evidence):
        raise ValueError("missing_evidence must contain strings")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "tenant_id": state.tenant_id,
        "company_id": state.company_id,
        "customer_id": state.customer_id,
        "program_id": state.program_id,
        "contract_id": state.contract_id,
        "nomination_id": state.nomination_id,
        "forecast_units": str(state.forecast_units) if state.forecast_units is not None else None,
        "recovery_case": recovery_case_to_payload(state.recovery_case),
        "evidence_refs": list(state.evidence_refs),
        "missing_evidence": list(state.missing_evidence),
        "deadline": state.deadline,
    }
    canonical = _canonical_json(payload)
    checksum = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return _canonical_json({"checksum": checksum, "payload": payload})


def load_state(serialized: str, *, expected_tenant_id: str) -> AssistedCaseState:
    _validate_identifier("expected_tenant_id", expected_tenant_id)
    try:
        envelope = json.loads(serialized)
    except json.JSONDecodeError as exc:
        raise ValueError("state is not valid JSON") from exc

    if set(envelope) != {"checksum", "payload"}:
        raise ValueError("state envelope is invalid")
    payload = envelope["payload"]
    if not isinstance(payload, dict):
        raise ValueError("state payload is invalid")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported state schema version")

    expected_checksum = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    if envelope["checksum"] != expected_checksum:
        raise ValueError("state checksum mismatch")

    tenant_id = payload.get("tenant_id")
    if tenant_id != expected_tenant_id:
        raise PermissionError("tenant mismatch")

    for key in ("company_id", "customer_id", "program_id"):
        _validate_identifier(key, payload.get(key, ""))
    _validate_contract_anchor(payload.get("contract_id"), payload.get("nomination_id"))

    evidence_refs = payload.get("evidence_refs", [])
    missing_evidence = payload.get("missing_evidence", [])
    if not isinstance(evidence_refs, list) or not all(isinstance(item, str) for item in evidence_refs):
        raise ValueError("evidence_refs must be a string list")
    if not isinstance(missing_evidence, list) or not all(isinstance(item, str) for item in missing_evidence):
        raise ValueError("missing_evidence must be a string list")

    forecast_raw = payload.get("forecast_units")
    forecast_units = Decimal(str(forecast_raw)) if forecast_raw is not None else None
    if forecast_units is not None and forecast_units < Decimal("0"):
        raise ValueError("forecast_units must be non-negative")

    return AssistedCaseState(
        tenant_id=tenant_id,
        company_id=payload["company_id"],
        customer_id=payload["customer_id"],
        program_id=payload["program_id"],
        recovery_case=recovery_case_from_payload(payload["recovery_case"]),
        evidence_refs=tuple(evidence_refs),
        missing_evidence=tuple(missing_evidence),
        deadline=payload.get("deadline"),
        contract_id=payload.get("contract_id"),
        nomination_id=payload.get("nomination_id"),
        forecast_units=forecast_units,
    )
