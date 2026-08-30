from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Mapping

from vertical_apps.aviation_recovery.service import AviationRecoveryService


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class AviationPilotIntakeError(ValueError):
    """Fail-closed intake error for real/synthetic assisted pilot evidence."""


@dataclass(frozen=True)
class EvidenceInput:
    source_ref: str
    sha256: str
    provenance: str
    authorized: bool

    @classmethod
    def create(
        cls,
        *,
        source_ref: str,
        sha256: str,
        provenance: str,
        authorized: bool,
    ) -> "EvidenceInput":
        ref = str(source_ref or "").strip()
        digest = str(sha256 or "").strip().lower()
        source = str(provenance or "").strip()
        if not ref:
            raise AviationPilotIntakeError("evidence source_ref is required")
        if not _SHA256.fullmatch(digest):
            raise AviationPilotIntakeError("evidence sha256 must be a 64-character hexadecimal digest")
        if not source:
            raise AviationPilotIntakeError("evidence provenance is required")
        if authorized is not True:
            raise AviationPilotIntakeError("evidence use is not authorized")
        return cls(source_ref=ref, sha256=digest, provenance=source, authorized=True)

    @property
    def immutable_ref(self) -> str:
        return f"{self.source_ref}@sha256:{self.sha256}"


class AviationPilotIntakeService:
    """Evidence-backed assisted-pilot boundary in front of the generic consumer."""

    def __init__(self, database):
        self.service = AviationRecoveryService(database)

    def analyze(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        lease_contract: EvidenceInput,
        maintenance_event: EvidenceInput,
        eligible_cost: str,
        reimbursed_amount: str,
        notice_due: date,
    ) -> Mapping[str, object]:
        if not str(tenant_id or "").strip() or not str(actor_id or "").strip():
            raise AviationPilotIntakeError("tenant_id and actor_id are required")
        if not isinstance(lease_contract, EvidenceInput) or not isinstance(maintenance_event, EvidenceInput):
            raise AviationPilotIntakeError("verified lease and maintenance evidence are required")
        if not lease_contract.authorized or not maintenance_event.authorized:
            raise AviationPilotIntakeError("all evidence must be explicitly authorized")

        result = self.service.analyze(
            tenant_id=tenant_id,
            actor_id=actor_id,
            contract_ref=lease_contract.immutable_ref,
            event_ref=maintenance_event.immutable_ref,
            eligible_cost=eligible_cost,
            reimbursed_amount=reimbursed_amount,
            notice_due=notice_due,
        )
        return {
            **result,
            "pilot_state": "CANDIDATE_READY_FOR_HUMAN_REVIEW" if result["state"] == "READY_FOR_REVIEW" else "EVIDENCE_OR_ECONOMICS_UNRESOLVED",
            "entitlement_state": "UNKNOWN",
            "recovery_state": "NOT_ESTABLISHED",
            "contract_evidence_sha256": lease_contract.sha256,
            "maintenance_evidence_sha256": maintenance_event.sha256,
            "contract_provenance": lease_contract.provenance,
            "maintenance_provenance": maintenance_event.provenance,
            "customer_permission_verified": True,
        }

    def review(self, **kwargs):
        return self.service.review(**kwargs)

    def action(self, **kwargs):
        return self.service.action(**kwargs)

    def resolve(self, **kwargs):
        return self.service.resolve(**kwargs)
