from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from factory_cloud.assurance_store import AssuranceStore
from factory_cloud.shared_contracts import EntitlementSnapshot, IdentityPrincipal
from factory_cloud.vertical_runtime import RecoveryVerticalRuntime


class AviationRecoveryService:
    """Assisted lessee-side maintenance-reserve recoverability service.

    This service stores only evidence/calculation/review metadata supplied to the
    application. It does not assert entitlement without explicit source evidence.
    """

    def __init__(self, database: str | Path):
        self.store = AssuranceStore(database)
        self.runtime = RecoveryVerticalRuntime()

    def analyze(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        contract_ref: str,
        event_ref: str,
        eligible_cost: str,
        reimbursed_amount: str,
        notice_due: date,
    ) -> dict[str, str]:
        principal = IdentityPrincipal.create(
            tenant_id=tenant_id,
            subject=actor_id,
            roles=("analyst",),
            issuer="aviation-recovery",
            audience="aviation-recovery",
        )
        entitlement = EntitlementSnapshot.create(
            tenant_id=tenant_id,
            plan_id="assisted-pilot",
            status="ACTIVE",
            features=(RecoveryVerticalRuntime.FEATURE,),
        )
        result = self.runtime.aviation(
            principal=principal,
            entitlement=entitlement,
            contract_ref=contract_ref,
            event_ref=event_ref,
            eligible_cost=Decimal(eligible_cost),
            reimbursed_amount=Decimal(reimbursed_amount),
            notice_due=notice_due,
        )
        self.store.persist_case(
            evidence=result.evidence,
            calculation=result.calculation,
            deadline=result.deadline,
            finding=result.finding,
            audit=result.audit,
            notification=result.notification,
        )
        return {
            "finding_id": result.finding.finding_id,
            "state": result.finding.state,
            "potential_value": result.calculation.output_value,
            "calculation_hash": result.calculation.reproducibility_hash,
            "deadline_state": result.deadline.state_on(date.today()),
        }
