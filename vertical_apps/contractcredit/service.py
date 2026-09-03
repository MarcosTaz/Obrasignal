from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from factory_cloud.assurance_ops import AssuranceOperations
from factory_cloud.assurance_store import AssuranceStore
from factory_cloud.recovery_index import RecoveryIndex
from factory_cloud.shared_contracts import EntitlementSnapshot, IdentityPrincipal
from factory_cloud.vertical_runtime import RecoveryVerticalRuntime


class ContractCreditService:
    """Assisted enterprise service-credit reconciliation service."""

    def __init__(self, database: str | Path):
        self.store = AssuranceStore(database)
        self.index = RecoveryIndex(database)
        self.runtime = RecoveryVerticalRuntime()
        self.ops = AssuranceOperations(self.store)

    def analyze(self, *, tenant_id: str, actor_id: str, contract_ref: str, incident_ref: str, monthly_fee: str, credit_rate: str, notice_due: date) -> dict[str, str]:
        principal = IdentityPrincipal.create(tenant_id=tenant_id, subject=actor_id, roles=("analyst",), issuer="contractcredit", audience="contractcredit")
        entitlement = EntitlementSnapshot.create(tenant_id=tenant_id, plan_id="assisted-pilot", status="ACTIVE", features=(RecoveryVerticalRuntime.FEATURE,))
        result = self.runtime.contractcredit(principal=principal, entitlement=entitlement, contract_ref=contract_ref, incident_ref=incident_ref, monthly_fee=Decimal(monthly_fee), credit_rate=Decimal(credit_rate), notice_due=notice_due)
        is_new_recovery = self.index.persist_case_index(result.entitlement, result.fingerprint)
        self.store.persist_case(evidence=result.evidence, calculation=result.calculation, deadline=result.deadline, finding=result.finding, audit=result.audit, notification=result.notification)
        return {"finding_id": result.finding.finding_id, "state": result.finding.state, "potential_value": result.calculation.output_value, "calculation_hash": result.calculation.reproducibility_hash, "deadline_state": result.deadline.state_on(date.today()), "recovery_fingerprint": result.fingerprint.fingerprint, "new_recovery_record": str(is_new_recovery).lower()}

    def review(self, *, tenant_id: str, finding_id: str, reviewer: str, approved: bool, reason: str) -> str:
        return self.ops.review(tenant_id=tenant_id, finding_id=finding_id, reviewer=reviewer, approved=approved, reason=reason)

    def action(self, *, tenant_id: str, finding_id: str) -> str:
        return self.ops.action(tenant_id=tenant_id, finding_id=finding_id)

    def resolve(self, *, tenant_id: str, finding_id: str, outcome_id: str, recovered_amount: str, currency: str, evidence_ref: str):
        return self.ops.resolve(tenant_id=tenant_id, finding_id=finding_id, outcome_id=outcome_id, recovered_amount=recovered_amount, currency=currency, evidence_ref=evidence_ref)
