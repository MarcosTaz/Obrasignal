from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Mapping

from vertical_apps.contractcredit.service import ContractCreditService


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ContractCreditPilotIntakeError(ValueError):
    pass


@dataclass(frozen=True)
class EvidenceInput:
    source_ref: str
    sha256: str
    provenance: str
    authorized: bool

    @classmethod
    def create(cls, *, source_ref: str, sha256: str, provenance: str, authorized: bool) -> "EvidenceInput":
        ref = str(source_ref or "").strip()
        digest = str(sha256 or "").strip().lower()
        source = str(provenance or "").strip()
        if not ref:
            raise ContractCreditPilotIntakeError("evidence source_ref is required")
        if not _SHA256.fullmatch(digest):
            raise ContractCreditPilotIntakeError("evidence sha256 must be a 64-character hexadecimal digest")
        if not source:
            raise ContractCreditPilotIntakeError("evidence provenance is required")
        if authorized is not True:
            raise ContractCreditPilotIntakeError("evidence use is not authorized")
        return cls(source_ref=ref, sha256=digest, provenance=source, authorized=True)

    @property
    def immutable_ref(self) -> str:
        return f"{self.source_ref}@sha256:{self.sha256}"


class ContractCreditPilotIntakeService:
    """Evidence-backed boundary for real assisted service-credit candidates."""

    def __init__(self, database):
        self.service = ContractCreditService(database)

    def analyze(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        service_contract: EvidenceInput,
        incident_evidence: EvidenceInput,
        monthly_fee: str,
        credit_rate: str,
        notice_due: date,
    ) -> Mapping[str, object]:
        if not str(tenant_id or "").strip() or not str(actor_id or "").strip():
            raise ContractCreditPilotIntakeError("tenant_id and actor_id are required")
        if not isinstance(service_contract, EvidenceInput) or not isinstance(incident_evidence, EvidenceInput):
            raise ContractCreditPilotIntakeError("verified contract and incident evidence are required")
        if not service_contract.authorized or not incident_evidence.authorized:
            raise ContractCreditPilotIntakeError("all evidence must be explicitly authorized")

        result = self.service.analyze(
            tenant_id=tenant_id,
            actor_id=actor_id,
            contract_ref=service_contract.immutable_ref,
            incident_ref=incident_evidence.immutable_ref,
            monthly_fee=monthly_fee,
            credit_rate=credit_rate,
            notice_due=notice_due,
        )
        return {
            **result,
            "pilot_state": "CANDIDATE_READY_FOR_HUMAN_REVIEW" if result["state"] == "READY_FOR_REVIEW" else "EVIDENCE_OR_ECONOMICS_UNRESOLVED",
            "entitlement_state": "UNKNOWN",
            "breach_state": "NOT_ESTABLISHED",
            "recovery_state": "NOT_ESTABLISHED",
            "contract_evidence_sha256": service_contract.sha256,
            "incident_evidence_sha256": incident_evidence.sha256,
            "contract_provenance": service_contract.provenance,
            "incident_provenance": incident_evidence.provenance,
            "customer_permission_verified": True,
        }

    def review(self, **kwargs):
        return self.service.review(**kwargs)

    def action(self, **kwargs):
        return self.service.action(**kwargs)

    def resolve(self, **kwargs):
        return self.service.resolve(**kwargs)
