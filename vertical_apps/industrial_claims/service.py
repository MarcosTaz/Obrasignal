from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from factory_cloud.assurance_kernel import (
    AssuranceKernelError,
    CalculationInput,
    CalculationRecord,
    DeadlineWindow,
    EvidenceEnvelope,
    FindingRecord,
    assert_same_tenant,
)
from factory_cloud.assurance_ops import AssuranceOperations
from factory_cloud.assurance_store import AssuranceStore
from factory_cloud.document_store import DocumentStore, StoredDocument
from factory_cloud.recovery_index import RecoveryIndex
from factory_cloud.recovery_primitives import EntitlementBasis, RecoveryFingerprint
from factory_cloud.shared_platform import AuditEvent, NotificationEvent, TenantContext, assert_tenant_context


ALLOWED_CLAIM_FAMILIES = {
    "EXCESS_OBSOLETE_RAW_MATERIAL",
    "WIP",
    "FINISHED_GOODS",
    "TOOLING",
    "NRE",
    "DEDICATED_INVESTMENT",
    "SUPPLIER_COMMITMENT",
    "MITIGATION_COST",
    "OTHER_DOCUMENTED_PROGRAM_EXPOSURE",
}


@dataclass(frozen=True)
class IndustrialClaimResult:
    tenant_id: str
    claim_family: str
    evidence: tuple[EvidenceEnvelope, ...]
    entitlement: EntitlementBasis
    fingerprint: RecoveryFingerprint
    calculation: CalculationRecord
    deadline: DeadlineWindow
    finding: FindingRecord
    audit: AuditEvent
    notification: NotificationEvent
    missing_evidence: tuple[str, ...]
    is_new_recovery: bool


class IndustrialClaimsService:
    """Assisted supplier-side industrial claim reconstruction.

    Cost is never treated as money owed by itself. A reviewable finding requires
    explicit commercial-basis evidence plus event and cost evidence. Formula
    version 1 computes net potential only; it does not make a legal conclusion.
    """

    vertical = "industrial-claims"

    def __init__(self, database: str | Path, document_root: str | Path | None = None):
        database_path = Path(database)
        self.store = AssuranceStore(database_path)
        self.index = RecoveryIndex(database_path)
        self.ops = AssuranceOperations(self.store)
        self.documents = DocumentStore(document_root or Path(str(database_path) + ".documents"))

    @staticmethod
    def _id(tenant_id: str, local: str) -> str:
        return f"{tenant_id}:{local}"

    def ingest_document(
        self,
        *,
        tenant_id: str,
        document_id: str,
        source_ref: str,
        original_name: str,
        content: bytes,
    ) -> StoredDocument:
        return self.documents.put(
            tenant_id=tenant_id,
            document_id=document_id,
            source_ref=source_ref,
            original_name=original_name,
            content=content,
        )

    def read_document(self, *, tenant_id: str, document_id: str) -> tuple[StoredDocument, bytes]:
        return self.documents.get(tenant_id=tenant_id, document_id=document_id)

    @staticmethod
    def _decimal(name: str, value: str) -> Decimal:
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise AssuranceKernelError(f"invalid decimal input: {name}") from exc

    def analyze(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        customer_ref: str,
        program_ref: str,
        event_ref: str,
        claim_family: str,
        commercial_basis_ref: str,
        cost_evidence_ref: str,
        gross_cost: str,
        avoided_cost: str = "0",
        resale_reuse: str = "0",
        third_party_recovery: str = "0",
        prior_payment: str = "0",
        other_mitigation: str = "0",
        notice_due: date | None = None,
        missing_evidence: tuple[str, ...] = (),
        commercial_basis_document_id: str | None = None,
        event_document_id: str | None = None,
        cost_document_id: str | None = None,
    ) -> IndustrialClaimResult:
        context = TenantContext(tenant_id=tenant_id, actor_id=actor_id, roles=("analyst",))
        context.require_role("analyst")
        family = claim_family.strip().upper()
        if family not in ALLOWED_CLAIM_FAMILIES:
            raise AssuranceKernelError("unsupported industrial claim family")
        refs = (customer_ref, program_ref, event_ref, commercial_basis_ref, cost_evidence_ref)
        if any(not str(value).strip() for value in refs):
            raise AssuranceKernelError("customer, program, event, commercial basis and cost evidence are required")

        amounts = {
            "gross_cost": self._decimal("gross_cost", gross_cost),
            "avoided_cost": self._decimal("avoided_cost", avoided_cost),
            "resale_reuse": self._decimal("resale_reuse", resale_reuse),
            "third_party_recovery": self._decimal("third_party_recovery", third_party_recovery),
            "prior_payment": self._decimal("prior_payment", prior_payment),
            "other_mitigation": self._decimal("other_mitigation", other_mitigation),
        }
        if any(value < 0 for value in amounts.values()):
            raise AssuranceKernelError("industrial claim amounts cannot be negative")
        deductions = sum((value for key, value in amounts.items() if key != "gross_cost"), Decimal("0"))
        net_potential = amounts["gross_cost"] - deductions
        if net_potential < 0:
            raise AssuranceKernelError("mitigation/recovery cannot exceed gross cost without review")

        document_ids = (commercial_basis_document_id, event_document_id, cost_document_id)
        if any(document_ids) and not all(document_ids):
            raise AssuranceKernelError("commercial basis, event and cost document ids must be supplied together")
        if all(document_ids):
            basis_doc, basis_content = self.read_document(tenant_id=tenant_id, document_id=str(commercial_basis_document_id))
            event_doc, event_content = self.read_document(tenant_id=tenant_id, document_id=str(event_document_id))
            cost_doc, cost_content = self.read_document(tenant_id=tenant_id, document_id=str(cost_document_id))
            basis_source_ref = basis_doc.source_ref
            event_source_ref = event_doc.source_ref
            cost_source_ref = cost_doc.source_ref
            basis_payload: bytes | str = basis_content
            event_payload: bytes | str = event_content
            cost_payload: bytes | str = cost_content
        else:
            basis_source_ref = commercial_basis_ref
            event_source_ref = event_ref
            cost_source_ref = cost_evidence_ref
            basis_payload = f"commercial-basis:{customer_ref}:{program_ref}:{commercial_basis_ref}"
            event_payload = f"event:{customer_ref}:{program_ref}:{event_ref}"
            cost_payload = f"cost:{family}:{gross_cost}:{cost_evidence_ref}"

        basis = EvidenceEnvelope.create(
            evidence_id=self._id(tenant_id, f"{commercial_basis_ref}:commercial-basis"),
            tenant_id=tenant_id,
            source_type="commercial_basis",
            source_ref=basis_source_ref,
            content=basis_payload,
            metadata={"stored_document_id": commercial_basis_document_id} if commercial_basis_document_id else {},
        )
        event = EvidenceEnvelope.create(
            evidence_id=self._id(tenant_id, f"{event_ref}:event"),
            tenant_id=tenant_id,
            source_type="industrial_commercial_event",
            source_ref=event_source_ref,
            content=event_payload,
            metadata={"stored_document_id": event_document_id} if event_document_id else {},
        )
        cost = EvidenceEnvelope.create(
            evidence_id=self._id(tenant_id, f"{cost_evidence_ref}:cost"),
            tenant_id=tenant_id,
            source_type="cost_evidence",
            source_ref=cost_source_ref,
            content=cost_payload,
            metadata={"stored_document_id": cost_document_id} if cost_document_id else {},
        )
        evidence = (basis, event, cost)

        entitlement = EntitlementBasis.create(
            entitlement_id=self._id(tenant_id, f"{event_ref}:{family}:basis"),
            tenant_id=tenant_id,
            domain=self.vertical,
            source_evidence_ids=tuple(item.evidence_id for item in evidence),
            rule_ref="documented-commercial-basis-v1",
            confidence="SUPPORTED" if not missing_evidence else "PARTIAL",
        )
        fingerprint = RecoveryFingerprint.create(
            tenant_id=tenant_id,
            vertical=self.vertical,
            contract_ref=f"{customer_ref}:{program_ref}:{commercial_basis_ref}",
            event_ref=event_ref,
            remedy_type=family.lower(),
        )

        calculation = CalculationRecord.create(
            calculation_id=self._id(tenant_id, f"{event_ref}:{family}:net-potential"),
            tenant_id=tenant_id,
            formula_id="industrial_net_potential_claim",
            formula_version="1",
            inputs=tuple(
                CalculationInput(
                    name=name,
                    value=str(value),
                    unit="currency",
                    evidence_ids=(cost.evidence_id, basis.evidence_id),
                )
                for name, value in amounts.items()
            ),
            output_value=net_potential,
            output_unit="currency",
        )
        deadline = DeadlineWindow.create(
            deadline_id=self._id(tenant_id, f"{event_ref}:{family}:notice"),
            tenant_id=tenant_id,
            due_date=notice_due or date.max,
            basis_evidence_ids=(basis.evidence_id, event.evidence_id),
        )

        state = "READY_FOR_REVIEW" if entitlement.actionable and net_potential > 0 else "UNRESOLVED_EVIDENCE"
        finding = FindingRecord.create(
            finding_id=self._id(tenant_id, f"{event_ref}:{family}:finding"),
            tenant_id=tenant_id,
            finding_type="industrial_recovery_candidate",
            evidence_ids=tuple(item.evidence_id for item in evidence),
            calculation_ids=(calculation.calculation_id,),
            state=state,
        )
        assert_same_tenant(*evidence, calculation, deadline, finding)
        assert_tenant_context(context, *evidence, calculation, deadline, finding)
        audit = AuditEvent.create(
            event_id=self._id(tenant_id, f"{event_ref}:{family}:audit"),
            context=context,
            event_type="industrial_finding_created",
            subject_ref=finding.finding_id,
            evidence_refs=finding.evidence_ids,
            payload={
                "claim_family": family,
                "calculation_hash": calculation.reproducibility_hash,
                "entitlement_basis_hash": entitlement.basis_hash,
                "recovery_fingerprint": fingerprint.fingerprint,
                "missing_evidence": sorted(set(missing_evidence)),
                "stored_document_ids": [item for item in document_ids if item],
            },
        )
        notification = NotificationEvent.create(
            event_id=self._id(tenant_id, f"{event_ref}:{family}:notification"),
            tenant_id=tenant_id,
            event_type="finding_ready" if state == "READY_FOR_REVIEW" else "finding_unresolved",
            subject_ref=finding.finding_id,
            payload={"vertical": self.vertical, "claim_family": family, "state": state},
        )

        is_new = self.index.persist_case_index(entitlement, fingerprint)
        self.store.persist_case(
            evidence=evidence,
            calculation=calculation,
            deadline=deadline,
            finding=finding,
            audit=audit,
            notification=notification,
        )
        return IndustrialClaimResult(
            tenant_id=tenant_id,
            claim_family=family,
            evidence=evidence,
            entitlement=entitlement,
            fingerprint=fingerprint,
            calculation=calculation,
            deadline=deadline,
            finding=finding,
            audit=audit,
            notification=notification,
            missing_evidence=tuple(sorted(set(missing_evidence))),
            is_new_recovery=is_new,
        )

    def review(self, *, tenant_id: str, finding_id: str, reviewer: str, approved: bool, reason: str) -> str:
        return self.ops.review(tenant_id=tenant_id, finding_id=finding_id, reviewer=reviewer, approved=approved, reason=reason)

    def action(self, *, tenant_id: str, finding_id: str) -> str:
        return self.ops.action(tenant_id=tenant_id, finding_id=finding_id)

    def resolve(self, *, tenant_id: str, finding_id: str, outcome_id: str, recovered_amount: str, currency: str, evidence_ref: str):
        return self.ops.resolve(
            tenant_id=tenant_id,
            finding_id=finding_id,
            outcome_id=outcome_id,
            recovered_amount=recovered_amount,
            currency=currency,
            evidence_ref=evidence_ref,
        )
