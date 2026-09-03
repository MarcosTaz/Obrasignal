from __future__ import annotations

from datetime import date
from decimal import Decimal

from factory_cloud.shared_contracts import EntitlementSnapshot, IdentityPrincipal, SharedContractError
from factory_cloud.shared_platform import TenantContext
from factory_cloud.vertical_consumers import (
    AviationLeaseRecoveryConsumer,
    ContractCreditRecoveryConsumer,
    RecoveryCaseResult,
)


class RecoveryVerticalRuntime:
    """Shared authorization/entitlement boundary for assisted recovery verticals."""

    FEATURE = "assurance_analysis"

    @staticmethod
    def _context(principal: IdentityPrincipal, entitlement: EntitlementSnapshot) -> TenantContext:
        if principal.tenant_id != entitlement.tenant_id:
            raise SharedContractError("identity and entitlement tenant mismatch")
        principal.require("analyst")
        entitlement.require(RecoveryVerticalRuntime.FEATURE)
        return TenantContext(principal.tenant_id, principal.subject, principal.roles)

    def aviation(
        self,
        *,
        principal: IdentityPrincipal,
        entitlement: EntitlementSnapshot,
        contract_ref: str,
        event_ref: str,
        eligible_cost: Decimal,
        reimbursed_amount: Decimal,
        notice_due: date,
    ) -> RecoveryCaseResult:
        return AviationLeaseRecoveryConsumer().evaluate(
            context=self._context(principal, entitlement),
            contract_ref=contract_ref,
            event_ref=event_ref,
            eligible_cost=eligible_cost,
            reimbursed_amount=reimbursed_amount,
            notice_due=notice_due,
        )

    def contractcredit(
        self,
        *,
        principal: IdentityPrincipal,
        entitlement: EntitlementSnapshot,
        contract_ref: str,
        incident_ref: str,
        monthly_fee: Decimal,
        credit_rate: Decimal,
        notice_due: date,
    ) -> RecoveryCaseResult:
        return ContractCreditRecoveryConsumer().evaluate(
            context=self._context(principal, entitlement),
            contract_ref=contract_ref,
            incident_ref=incident_ref,
            monthly_fee=monthly_fee,
            credit_rate=credit_rate,
            notice_due=notice_due,
        )
