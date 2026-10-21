from datetime import date
from decimal import Decimal

import pytest

from factory_cloud.shared_contracts import EntitlementSnapshot, IdentityPrincipal, SharedContractError
from factory_cloud.vertical_runtime import RecoveryVerticalRuntime


def _principal(tenant="tenant"):
    return IdentityPrincipal.create(
        tenant_id=tenant, subject="analyst", roles=("analyst",), issuer="issuer", audience="recovery"
    )


def _entitlement(tenant="tenant", status="ACTIVE"):
    return EntitlementSnapshot.create(
        tenant_id=tenant, plan_id="pilot", status=status, features=("assurance_analysis",)
    )


def test_same_identity_entitlement_contract_runs_aviation_and_contractcredit():
    runtime = RecoveryVerticalRuntime()
    aviation = runtime.aviation(
        principal=_principal("airline"), entitlement=_entitlement("airline"),
        contract_ref="lease", event_ref="event",
        eligible_cost=Decimal("100"), reimbursed_amount=Decimal("10"), notice_due=date(2026, 9, 30),
    )
    credit = runtime.contractcredit(
        principal=_principal("enterprise"), entitlement=_entitlement("enterprise"),
        contract_ref="msa", incident_ref="inc",
        monthly_fee=Decimal("1000"), credit_rate=Decimal("0.1"), notice_due=date(2026, 9, 15),
    )
    assert aviation.tenant_id == "airline"
    assert credit.tenant_id == "enterprise"
    assert aviation.vertical != credit.vertical


def test_runtime_rejects_cross_tenant_identity_entitlement():
    with pytest.raises(SharedContractError, match="tenant mismatch"):
        RecoveryVerticalRuntime().aviation(
            principal=_principal("a"), entitlement=_entitlement("b"),
            contract_ref="lease", event_ref="event",
            eligible_cost=Decimal("1"), reimbursed_amount=Decimal("0"), notice_due=date(2026, 9, 30),
        )


def test_runtime_rejects_suspended_entitlement():
    with pytest.raises(SharedContractError, match="denied"):
        RecoveryVerticalRuntime().contractcredit(
            principal=_principal(), entitlement=_entitlement(status="SUSPENDED"),
            contract_ref="msa", incident_ref="inc",
            monthly_fee=Decimal("1000"), credit_rate=Decimal("0.1"), notice_due=date(2026, 9, 15),
        )
