from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

from .engine import CommitmentState, CostRecoveryMode, ExposureType, RecoveryCase


SCHEMA_VERSION = 4
_STATE_PAYLOAD_FIELDS_V2 = {
    "schema_version",
    "tenant_id",
    "company_id",
    "customer_id",
    "program_id",
    "contract_id",
    "nomination_id",
    "forecast_units",
    "recovery_case",
    "evidence_refs",
    "missing_evidence",
    "deadline",
}
_STATE_PAYLOAD_FIELDS_V3 = _STATE_PAYLOAD_FIELDS_V2 | {"period_id", "unit"}
_STATE_PAYLOAD_FIELDS_V4 = _STATE_PAYLOAD_FIELDS_V3 | {"fact_refs"}
_PERSISTED_RECOVERY_CASE_FIELDS = set(RecoveryCase.__dataclass_fields__)


@dataclass(frozen=True)
class AssistedCaseState:
    tenant_id: str
    company_id: str
    customer_id: str
    program_id: str
    recovery_case: RecoveryCase
    period_id: Optional[str] = None
    unit: Optional[str] = None
    evidence_refs: Tuple[str, ...] = ()
    fact_refs: Tuple[str, ...] = ()
    missing_evidence: Tuple[str, ...] = ()
    deadline: Optional[str] = None
    contract_id: Optional[str] = None
    nomination_id: Optional[str] = None
    forecast_units: Optional[Decimal] = None


def exact_decimal_from_input(value, *, field_name: str) -> Decimal:
    """Parse an exact decimal boundary value without accepting binary floats."""

    if type(value) is int:
        raw = str(value)
    elif isinstance(value, str):
        raw = value
    else:
        raise ValueError(f"{field_name} must be an exact decimal string or integer")
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc


def _validate_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    if len(value) > 200:
        raise ValueError(f"{name} must be at most 200 characters")


def _validate_optional_context(name: str, value: Optional[str]) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string or null")
    if value != value.strip():
        raise ValueError(f"{name} must not contain leading/trailing whitespace")
    if len(value) > 200:
        raise ValueError(f"{name} must be at most 200 characters")


def _validate_contract_anchor(contract_id: Optional[str], nomination_id: Optional[str]) -> None:
    contract = (contract_id or "").strip() if isinstance(contract_id, (str, type(None))) else ""
    nomination = (nomination_id or "").strip() if isinstance(nomination_id, (str, type(None))) else ""
    if contract_id is not None and not isinstance(contract_id, str):
        raise ValueError("contract_id must be a string or null")
    if nomination_id is not None and not isinstance(nomination_id, str):
        raise ValueError("nomination_id must be a string or null")
    if len(contract) > 200 or len(nomination) > 200:
        raise ValueError("contract_id and nomination_id must be at most 200 characters")
    if not contract and not nomination:
        raise ValueError("contract_id or nomination_id is required")


def _validate_reference_list(name: str, values) -> None:
    if not isinstance(values, (tuple, list)) or not all(isinstance(item, str) for item in values):
        raise ValueError(f"{name} must contain strings")
    if len(values) > 200:
        raise ValueError(f"{name} cannot exceed 200 references")
    normalized = [item.strip() for item in values]
    if any(not item for item in normalized):
        raise ValueError(f"{name} cannot contain blank references")
    if any(len(item) > 500 for item in normalized):
        raise ValueError(f"{name} references must be at most 500 characters")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} cannot contain duplicate references")


def _validate_evidence_consistency(recovery_case: RecoveryCase, evidence_refs, fact_refs) -> None:
    if recovery_case.evidence_supported and not evidence_refs:
        raise ValueError("evidence_supported requires at least one persisted evidence reference")
    if fact_refs and not evidence_refs:
        raise ValueError("fact_refs require persisted evidence_refs")


def _validate_deadline(deadline: Optional[str], recovery_case: RecoveryCase) -> None:
    if deadline is not None:
        if not isinstance(deadline, str) or not deadline.strip():
            raise ValueError("deadline must be an ISO date or null")
        if deadline != deadline.strip():
            raise ValueError("deadline must be canonical YYYY-MM-DD")
        try:
            parsed = date.fromisoformat(deadline)
        except ValueError as exc:
            raise ValueError("deadline must be canonical YYYY-MM-DD") from exc
        if parsed.isoformat() != deadline:
            raise ValueError("deadline must be canonical YYYY-MM-DD")
    if recovery_case.notice_window_verified is True and deadline is None:
        raise ValueError("notice_window_verified requires a persisted ISO deadline")


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
        "mitigation",
        "prior_payment",
        "commitment_state",
        "exposure_type",
        "cost_recovery_mode",
        "evidence_supported",
        "asset_dedicated",
        "already_fully_amortized",
        "already_paid",
        "duplicate_claim",
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
        values[key] = exact_decimal_from_input(values[key], field_name=key)

    required_bool_fields = (
        "evidence_supported",
        "asset_dedicated",
        "already_fully_amortized",
        "already_paid",
        "duplicate_claim",
    )
    optional_bool_fields = (
        "explicit_recovery_right",
        "notice_valid",
        "customer_matches",
        "program_matches",
        "period_matches",
        "currency_matches",
        "unit_matches",
        "actuals_complete",
        "actuals_deduplicated",
        "cancelled_orders_excluded",
        "amortization_verified",
        "asset_dedication_verified",
        "mitigation_reviewed",
        "prior_recovery_reviewed",
        "notice_window_verified",
        "contract_matches",
        "contract_current",
        "amendment_reviewed",
        "amendment_matches",
        "duplicate_claim_reviewed",
    )
    for key in required_bool_fields:
        if type(values[key]) is not bool:
            raise ValueError(f"{key} must be boolean")
    for key in optional_bool_fields:
        if key in values and values[key] is not None and type(values[key]) is not bool:
            raise ValueError(f"{key} must be boolean or null")

    try:
        values["commitment_state"] = CommitmentState(values["commitment_state"])
        values["exposure_type"] = ExposureType(values["exposure_type"])
        values["cost_recovery_mode"] = CostRecoveryMode(values["cost_recovery_mode"])
    except ValueError as exc:
        raise ValueError("invalid recovery_case enum value") from exc
    return RecoveryCase(**values)


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def dump_state(state: AssistedCaseState) -> str:
    for name in ("tenant_id", "company_id", "customer_id", "program_id"):
        _validate_identifier(name, getattr(state, name))
    _validate_optional_context("period_id", state.period_id)
    _validate_optional_context("unit", state.unit)
    _validate_contract_anchor(state.contract_id, state.nomination_id)
    if state.forecast_units is not None:
        if not isinstance(state.forecast_units, Decimal) or not state.forecast_units.is_finite():
            raise ValueError("forecast_units must be a finite Decimal value")
        if state.forecast_units < Decimal("0"):
            raise ValueError("forecast_units must be non-negative")
    _validate_reference_list("evidence_refs", state.evidence_refs)
    _validate_reference_list("fact_refs", state.fact_refs)
    _validate_reference_list("missing_evidence", state.missing_evidence)
    _validate_evidence_consistency(state.recovery_case, state.evidence_refs, state.fact_refs)
    _validate_deadline(state.deadline, state.recovery_case)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "tenant_id": state.tenant_id,
        "company_id": state.company_id,
        "customer_id": state.customer_id,
        "program_id": state.program_id,
        "period_id": state.period_id,
        "unit": state.unit,
        "contract_id": state.contract_id,
        "nomination_id": state.nomination_id,
        "forecast_units": str(state.forecast_units) if state.forecast_units is not None else None,
        "recovery_case": recovery_case_to_payload(state.recovery_case),
        "evidence_refs": list(state.evidence_refs),
        "fact_refs": list(state.fact_refs),
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

    if not isinstance(envelope, dict) or set(envelope) != {"checksum", "payload"}:
        raise ValueError("state envelope is invalid")
    payload = envelope["payload"]
    if not isinstance(payload, dict):
        raise ValueError("state payload is invalid")

    version = payload.get("schema_version")
    if version == 2:
        expected_fields = _STATE_PAYLOAD_FIELDS_V2
    elif version == 3:
        expected_fields = _STATE_PAYLOAD_FIELDS_V3
    elif version == 4:
        expected_fields = _STATE_PAYLOAD_FIELDS_V4
    else:
        raise ValueError("unsupported state schema version")
    if set(payload) != expected_fields:
        raise ValueError(f"state payload fields do not match schema version {version}")

    expected_checksum = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    if envelope["checksum"] != expected_checksum:
        raise ValueError("state checksum mismatch")

    tenant_id = payload["tenant_id"]
    if tenant_id != expected_tenant_id:
        raise PermissionError("tenant mismatch")

    for key in ("company_id", "customer_id", "program_id"):
        _validate_identifier(key, payload[key])
    period_id = payload.get("period_id") if version >= 3 else None
    unit = payload.get("unit") if version >= 3 else None
    fact_refs = payload.get("fact_refs", []) if version >= 4 else []
    _validate_optional_context("period_id", period_id)
    _validate_optional_context("unit", unit)
    _validate_contract_anchor(payload["contract_id"], payload["nomination_id"])

    evidence_refs = payload["evidence_refs"]
    missing_evidence = payload["missing_evidence"]
    _validate_reference_list("evidence_refs", evidence_refs)
    _validate_reference_list("fact_refs", fact_refs)
    _validate_reference_list("missing_evidence", missing_evidence)

    forecast_raw = payload["forecast_units"]
    if forecast_raw is None:
        forecast_units = None
    else:
        forecast_units = exact_decimal_from_input(forecast_raw, field_name="forecast_units")
        if not forecast_units.is_finite() or forecast_units < Decimal("0"):
            raise ValueError("forecast_units must be a finite non-negative value")

    recovery_raw = payload["recovery_case"]
    if not isinstance(recovery_raw, dict) or set(recovery_raw) != _PERSISTED_RECOVERY_CASE_FIELDS:
        raise ValueError("persisted recovery_case fields do not match current schema")
    recovery_case = recovery_case_from_payload(recovery_raw)
    _validate_evidence_consistency(recovery_case, evidence_refs, fact_refs)
    _validate_deadline(payload["deadline"], recovery_case)

    return AssistedCaseState(
        tenant_id=tenant_id,
        company_id=payload["company_id"],
        customer_id=payload["customer_id"],
        program_id=payload["program_id"],
        period_id=period_id,
        unit=unit,
        recovery_case=recovery_case,
        evidence_refs=tuple(evidence_refs),
        fact_refs=tuple(fact_refs),
        missing_evidence=tuple(missing_evidence),
        deadline=payload["deadline"],
        contract_id=payload["contract_id"],
        nomination_id=payload["nomination_id"],
        forecast_units=forecast_units,
    )
