from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable


class RecoveryPrimitiveError(RuntimeError):
    pass


def _hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EntitlementBasis:
    entitlement_id: str
    tenant_id: str
    domain: str
    source_evidence_ids: tuple[str, ...]
    rule_ref: str
    confidence: str
    basis_hash: str

    @classmethod
    def create(cls, *, entitlement_id: str, tenant_id: str, domain: str, source_evidence_ids: Iterable[str], rule_ref: str, confidence: str) -> "EntitlementBasis":
        evidence = tuple(sorted({str(item).strip() for item in source_evidence_ids if str(item).strip()}))
        if not entitlement_id.strip() or not tenant_id.strip() or not domain.strip() or not rule_ref.strip():
            raise RecoveryPrimitiveError("entitlement identity, tenant, domain and rule ref are required")
        if not evidence:
            raise RecoveryPrimitiveError("entitlement basis requires source evidence")
        if confidence not in {"SUPPORTED", "PARTIAL", "UNRESOLVED"}:
            raise RecoveryPrimitiveError("invalid entitlement confidence")
        payload = {"domain": domain, "evidence": evidence, "rule_ref": rule_ref, "confidence": confidence}
        return cls(entitlement_id, tenant_id, domain, evidence, rule_ref, confidence, _hash(payload))

    @property
    def actionable(self) -> bool:
        return self.confidence == "SUPPORTED"


@dataclass(frozen=True)
class RecoveryFingerprint:
    tenant_id: str
    vertical: str
    contract_ref: str
    event_ref: str
    remedy_type: str
    fingerprint: str

    @classmethod
    def create(cls, *, tenant_id: str, vertical: str, contract_ref: str, event_ref: str, remedy_type: str) -> "RecoveryFingerprint":
        values = (tenant_id, vertical, contract_ref, event_ref, remedy_type)
        if any(not str(item).strip() for item in values):
            raise RecoveryPrimitiveError("recovery fingerprint fields are required")
        payload = {"tenant_id": tenant_id, "vertical": vertical, "contract_ref": contract_ref, "event_ref": event_ref, "remedy_type": remedy_type}
        return cls(tenant_id, vertical, contract_ref, event_ref, remedy_type, _hash(payload))


def duplicate_fingerprints(items: Iterable[RecoveryFingerprint]) -> tuple[str, ...]:
    counts: dict[tuple[str, str], int] = {}
    for item in items:
        key = (item.tenant_id, item.fingerprint)
        counts[key] = counts.get(key, 0) + 1
    return tuple(sorted(fingerprint for (_, fingerprint), count in counts.items() if count > 1))


@dataclass(frozen=True)
class FeeLineage:
    fee_id: str
    tenant_id: str
    outcome_id: str
    recovered_amount: str
    fee_rate: str
    fee_amount: str
    currency: str
    lineage_hash: str

    @classmethod
    def create(cls, *, fee_id: str, tenant_id: str, outcome_id: str, recovered_amount: str, fee_rate: str, currency: str) -> "FeeLineage":
        if not fee_id.strip() or not tenant_id.strip() or not outcome_id.strip() or not currency.strip():
            raise RecoveryPrimitiveError("fee identity, tenant, outcome and currency are required")
        try:
            recovered = Decimal(recovered_amount)
            rate = Decimal(fee_rate)
        except InvalidOperation as exc:
            raise RecoveryPrimitiveError("fee inputs must be decimal") from exc
        if recovered < 0 or rate < 0 or rate > 1:
            raise RecoveryPrimitiveError("invalid recovered amount or fee rate")
        fee = recovered * rate
        payload = {"outcome_id": outcome_id, "recovered_amount": str(recovered), "fee_rate": str(rate), "fee_amount": str(fee), "currency": currency}
        return cls(fee_id, tenant_id, outcome_id, str(recovered), str(rate), str(fee), currency, _hash(payload))
