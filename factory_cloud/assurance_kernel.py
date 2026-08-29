from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


class AssuranceKernelError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceEnvelope:
    evidence_id: str
    tenant_id: str
    source_type: str
    source_ref: str
    received_at: str
    content_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        evidence_id: str,
        tenant_id: str,
        source_type: str,
        source_ref: str,
        content: bytes | str,
        metadata: dict[str, Any] | None = None,
        received_at: str | None = None,
    ) -> "EvidenceEnvelope":
        values = [evidence_id, tenant_id, source_type, source_ref]
        if any(not str(value).strip() for value in values):
            raise AssuranceKernelError("evidence identity, tenant, source type and source ref are required")
        payload = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        return cls(
            evidence_id=str(evidence_id),
            tenant_id=str(tenant_id),
            source_type=str(source_type),
            source_ref=str(source_ref),
            received_at=received_at or datetime.now(timezone.utc).isoformat(),
            content_hash=hashlib.sha256(payload).hexdigest(),
            metadata=dict(metadata or {}),
        )


@dataclass(frozen=True)
class CalculationInput:
    name: str
    value: str
    unit: str | None = None
    evidence_ids: tuple[str, ...] = ()

    def decimal(self) -> Decimal:
        try:
            return Decimal(self.value)
        except InvalidOperation as exc:
            raise AssuranceKernelError(f"non-decimal calculation input: {self.name}") from exc


@dataclass(frozen=True)
class CalculationRecord:
    calculation_id: str
    tenant_id: str
    formula_id: str
    formula_version: str
    inputs: tuple[CalculationInput, ...]
    output_value: str
    output_unit: str | None
    evidence_ids: tuple[str, ...]
    reproducibility_hash: str

    @classmethod
    def create(
        cls,
        *,
        calculation_id: str,
        tenant_id: str,
        formula_id: str,
        formula_version: str,
        inputs: Iterable[CalculationInput],
        output_value: Decimal | int | float | str,
        output_unit: str | None = None,
    ) -> "CalculationRecord":
        items = tuple(inputs)
        if not calculation_id or not tenant_id or not formula_id or not formula_version:
            raise AssuranceKernelError("calculation identity, tenant, formula and version are required")
        if not items:
            raise AssuranceKernelError("calculation requires explicit inputs")
        evidence_ids = tuple(sorted({e for item in items for e in item.evidence_ids}))
        payload = {
            "formula_id": formula_id,
            "formula_version": formula_version,
            "inputs": [item.__dict__ for item in items],
            "output_value": str(output_value),
            "output_unit": output_unit,
        }
        return cls(
            calculation_id=calculation_id,
            tenant_id=tenant_id,
            formula_id=formula_id,
            formula_version=formula_version,
            inputs=items,
            output_value=str(output_value),
            output_unit=output_unit,
            evidence_ids=evidence_ids,
            reproducibility_hash=_sha256(payload),
        )


@dataclass(frozen=True)
class DeadlineWindow:
    deadline_id: str
    tenant_id: str
    due_date: date
    basis_evidence_ids: tuple[str, ...]
    timezone_name: str = "UTC"

    @classmethod
    def create(
        cls,
        *,
        deadline_id: str,
        tenant_id: str,
        due_date: date,
        basis_evidence_ids: Iterable[str],
        timezone_name: str = "UTC",
    ) -> "DeadlineWindow":
        evidence = tuple(sorted({str(x) for x in basis_evidence_ids if str(x)}))
        if not deadline_id or not tenant_id or not evidence:
            raise AssuranceKernelError("deadline requires tenant identity and supporting evidence")
        return cls(deadline_id, tenant_id, due_date, evidence, timezone_name)

    def state_on(self, on_date: date) -> str:
        if on_date < self.due_date:
            return "OPEN"
        if on_date == self.due_date:
            return "DUE_TODAY"
        return "EXPIRED"


ALLOWED_FINDING_STATES = {
    "UNRESOLVED_EVIDENCE",
    "READY_FOR_REVIEW",
    "APPROVED",
    "REJECTED",
    "ACTIONED",
    "RECOVERED",
    "CLOSED_NO_RECOVERY",
}


@dataclass(frozen=True)
class FindingRecord:
    finding_id: str
    tenant_id: str
    finding_type: str
    state: str
    evidence_ids: tuple[str, ...]
    calculation_ids: tuple[str, ...] = ()
    reviewer: str | None = None
    decision_reason: str | None = None

    @classmethod
    def create(
        cls,
        *,
        finding_id: str,
        tenant_id: str,
        finding_type: str,
        evidence_ids: Iterable[str],
        calculation_ids: Iterable[str] = (),
        state: str = "UNRESOLVED_EVIDENCE",
    ) -> "FindingRecord":
        evidence = tuple(sorted({str(x) for x in evidence_ids if str(x)}))
        calculations = tuple(sorted({str(x) for x in calculation_ids if str(x)}))
        if not finding_id or not tenant_id or not finding_type:
            raise AssuranceKernelError("finding identity, tenant and type are required")
        if state not in ALLOWED_FINDING_STATES:
            raise AssuranceKernelError(f"invalid finding state: {state}")
        if state != "UNRESOLVED_EVIDENCE" and not evidence:
            raise AssuranceKernelError("supported finding states require evidence")
        return cls(finding_id, tenant_id, finding_type, state, evidence, calculations)

    def review(self, *, reviewer: str, approved: bool, reason: str) -> "FindingRecord":
        if self.state != "READY_FOR_REVIEW":
            raise AssuranceKernelError("only READY_FOR_REVIEW findings may be reviewed")
        if not reviewer or not reason:
            raise AssuranceKernelError("reviewer and decision reason are required")
        return FindingRecord(
            self.finding_id,
            self.tenant_id,
            self.finding_type,
            "APPROVED" if approved else "REJECTED",
            self.evidence_ids,
            self.calculation_ids,
            reviewer,
            reason,
        )


def assert_same_tenant(*objects: Any) -> str:
    tenants = {str(getattr(obj, "tenant_id", "")) for obj in objects}
    if "" in tenants or len(tenants) != 1:
        raise AssuranceKernelError("cross-tenant evidence/calculation/finding composition rejected")
    return next(iter(tenants))
