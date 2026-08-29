from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from factory_cloud.assurance_kernel import AssuranceKernelError, CalculationInput, CalculationRecord, DeadlineWindow, EvidenceEnvelope, FindingRecord, assert_same_tenant
from factory_cloud.recovery_primitives import EntitlementBasis, RecoveryFingerprint
from factory_cloud.shared_platform import AuditEvent, InMemoryOutbox, NotificationEvent, TenantContext, assert_tenant_context


@dataclass(frozen=True)
class RecoveryCaseResult:
    vertical: str
    tenant_id: str
    evidence: tuple[EvidenceEnvelope, ...]
    entitlement: EntitlementBasis
    fingerprint: RecoveryFingerprint
    calculation: CalculationRecord
    deadline: DeadlineWindow
    finding: FindingRecord
    audit: AuditEvent
    notification: NotificationEvent


def _id(tenant_id: str, local_ref: str) -> str:
    return f"{tenant_id}:{local_ref}"


class AviationLeaseRecoveryConsumer:
    vertical = "aviation-lease-entitlement-recovery"

    def evaluate(self, *, context: TenantContext, contract_ref: str, event_ref: str, eligible_cost: Decimal, reimbursed_amount: Decimal, notice_due: date) -> RecoveryCaseResult:
        context.require_role("analyst", "reviewer")
        if eligible_cost < 0 or reimbursed_amount < 0:
            raise AssuranceKernelError("aviation amounts cannot be negative")
        contract = EvidenceEnvelope.create(evidence_id=_id(context.tenant_id, f"{contract_ref}:contract"), tenant_id=context.tenant_id, source_type="lease_contract", source_ref=contract_ref, content=f"lease:{contract_ref}")
        event = EvidenceEnvelope.create(evidence_id=_id(context.tenant_id, f"{event_ref}:maintenance"), tenant_id=context.tenant_id, source_type="maintenance_event", source_ref=event_ref, content=f"maintenance:{event_ref}:{eligible_cost}")
        entitlement = EntitlementBasis.create(entitlement_id=_id(context.tenant_id, f"{event_ref}:mr-basis"), tenant_id=context.tenant_id, domain=self.vertical, source_evidence_ids=(contract.evidence_id, event.evidence_id), rule_ref="lease-maintenance-reserve-term", confidence="SUPPORTED")
        fingerprint = RecoveryFingerprint.create(tenant_id=context.tenant_id, vertical=self.vertical, contract_ref=contract_ref, event_ref=event_ref, remedy_type="maintenance_reserve_reimbursement")
        unreimbursed = eligible_cost - reimbursed_amount
        calculation = CalculationRecord.create(
            calculation_id=_id(context.tenant_id, f"{event_ref}:recoverability"), tenant_id=context.tenant_id,
            formula_id="aviation_mr_unreimbursed_balance", formula_version="1",
            inputs=(CalculationInput("eligible_cost", str(eligible_cost), "currency", (event.evidence_id, contract.evidence_id)), CalculationInput("reimbursed_amount", str(reimbursed_amount), "currency", (event.evidence_id, contract.evidence_id))),
            output_value=unreimbursed, output_unit="currency",
        )
        deadline = DeadlineWindow.create(deadline_id=_id(context.tenant_id, f"{event_ref}:notice"), tenant_id=context.tenant_id, due_date=notice_due, basis_evidence_ids=(contract.evidence_id,))
        state = "READY_FOR_REVIEW" if unreimbursed > 0 and entitlement.actionable else "UNRESOLVED_EVIDENCE"
        finding = FindingRecord.create(finding_id=_id(context.tenant_id, f"{event_ref}:finding"), tenant_id=context.tenant_id, finding_type="maintenance_reserve_recoverability", evidence_ids=(contract.evidence_id, event.evidence_id), calculation_ids=(calculation.calculation_id,), state=state)
        assert_same_tenant(contract, event, calculation, deadline, finding)
        assert_tenant_context(context, contract, event, calculation, deadline, finding)
        audit = AuditEvent.create(event_id=_id(context.tenant_id, f"{event_ref}:audit"), context=context, event_type="finding_created", subject_ref=finding.finding_id, evidence_refs=finding.evidence_ids, payload={"vertical": self.vertical, "calculation_hash": calculation.reproducibility_hash, "entitlement_basis_hash": entitlement.basis_hash, "recovery_fingerprint": fingerprint.fingerprint})
        notification = NotificationEvent.create(event_id=_id(context.tenant_id, f"{event_ref}:notification"), tenant_id=context.tenant_id, event_type="finding_ready" if state == "READY_FOR_REVIEW" else "finding_unresolved", subject_ref=finding.finding_id, payload={"vertical": self.vertical, "state": state})
        InMemoryOutbox().add(notification)
        return RecoveryCaseResult(self.vertical, context.tenant_id, (contract, event), entitlement, fingerprint, calculation, deadline, finding, audit, notification)


class ContractCreditRecoveryConsumer:
    vertical = "contractcredit"

    def evaluate(self, *, context: TenantContext, contract_ref: str, incident_ref: str, monthly_fee: Decimal, credit_rate: Decimal, notice_due: date) -> RecoveryCaseResult:
        context.require_role("analyst", "reviewer")
        if monthly_fee < 0 or credit_rate < 0 or credit_rate > 1:
            raise AssuranceKernelError("invalid service-credit economic inputs")
        contract = EvidenceEnvelope.create(evidence_id=_id(context.tenant_id, f"{contract_ref}:contract"), tenant_id=context.tenant_id, source_type="service_contract", source_ref=contract_ref, content=f"service-contract:{contract_ref}")
        incident = EvidenceEnvelope.create(evidence_id=_id(context.tenant_id, f"{incident_ref}:incident"), tenant_id=context.tenant_id, source_type="service_incident", source_ref=incident_ref, content=f"incident:{incident_ref}:{monthly_fee}:{credit_rate}")
        entitlement = EntitlementBasis.create(entitlement_id=_id(context.tenant_id, f"{incident_ref}:credit-basis"), tenant_id=context.tenant_id, domain=self.vertical, source_evidence_ids=(contract.evidence_id, incident.evidence_id), rule_ref="service-level-credit-term", confidence="SUPPORTED")
        fingerprint = RecoveryFingerprint.create(tenant_id=context.tenant_id, vertical=self.vertical, contract_ref=contract_ref, event_ref=incident_ref, remedy_type="service_credit")
        potential_credit = monthly_fee * credit_rate
        calculation = CalculationRecord.create(
            calculation_id=_id(context.tenant_id, f"{incident_ref}:credit"), tenant_id=context.tenant_id,
            formula_id="service_credit_percentage_of_monthly_fee", formula_version="1",
            inputs=(CalculationInput("monthly_fee", str(monthly_fee), "currency", (contract.evidence_id,)), CalculationInput("credit_rate", str(credit_rate), "ratio", (contract.evidence_id, incident.evidence_id))),
            output_value=potential_credit, output_unit="currency",
        )
        deadline = DeadlineWindow.create(deadline_id=_id(context.tenant_id, f"{incident_ref}:notice"), tenant_id=context.tenant_id, due_date=notice_due, basis_evidence_ids=(contract.evidence_id, incident.evidence_id))
        state = "READY_FOR_REVIEW" if potential_credit > 0 and entitlement.actionable else "UNRESOLVED_EVIDENCE"
        finding = FindingRecord.create(finding_id=_id(context.tenant_id, f"{incident_ref}:finding"), tenant_id=context.tenant_id, finding_type="service_credit_candidate", evidence_ids=(contract.evidence_id, incident.evidence_id), calculation_ids=(calculation.calculation_id,), state=state)
        assert_same_tenant(contract, incident, calculation, deadline, finding)
        assert_tenant_context(context, contract, incident, calculation, deadline, finding)
        audit = AuditEvent.create(event_id=_id(context.tenant_id, f"{incident_ref}:audit"), context=context, event_type="finding_created", subject_ref=finding.finding_id, evidence_refs=finding.evidence_ids, payload={"vertical": self.vertical, "calculation_hash": calculation.reproducibility_hash, "entitlement_basis_hash": entitlement.basis_hash, "recovery_fingerprint": fingerprint.fingerprint})
        notification = NotificationEvent.create(event_id=_id(context.tenant_id, f"{incident_ref}:notification"), tenant_id=context.tenant_id, event_type="finding_ready" if state == "READY_FOR_REVIEW" else "finding_unresolved", subject_ref=finding.finding_id, payload={"vertical": self.vertical, "state": state})
        InMemoryOutbox().add(notification)
        return RecoveryCaseResult(self.vertical, context.tenant_id, (contract, incident), entitlement, fingerprint, calculation, deadline, finding, audit, notification)
