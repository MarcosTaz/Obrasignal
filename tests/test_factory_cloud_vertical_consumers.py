from datetime import date
from decimal import Decimal

import pytest

from factory_cloud.assurance_kernel import AssuranceKernelError
from factory_cloud.shared_platform import TenantContext
from factory_cloud.vertical_consumers import (
    AviationLeaseRecoveryConsumer,
    ContractCreditRecoveryConsumer,
)


def test_aviation_consumer_uses_shared_kernel_and_platform():
    context = TenantContext("airline-a", "analyst-1", ("analyst",))
    result = AviationLeaseRecoveryConsumer().evaluate(
        context=context,
        contract_ref="lease-001",
        event_ref="shop-visit-01",
        eligible_cost=Decimal("100000"),
        reimbursed_amount=Decimal("25000"),
        notice_due=date(2026, 9, 30),
    )
    assert result.vertical == "aviation-lease-entitlement-recovery"
    assert result.calculation.output_value == "75000"
    assert result.finding.state == "READY_FOR_REVIEW"
    assert result.audit.tenant_id == context.tenant_id
    assert result.notification.tenant_id == context.tenant_id
    assert len(result.calculation.evidence_ids) == 2


def test_contractcredit_consumer_uses_same_shared_contracts():
    context = TenantContext("enterprise-a", "analyst-2", ("analyst",))
    result = ContractCreditRecoveryConsumer().evaluate(
        context=context,
        contract_ref="msa-01",
        incident_ref="sev1-01",
        monthly_fee=Decimal("50000"),
        credit_rate=Decimal("0.10"),
        notice_due=date(2026, 9, 15),
    )
    assert result.vertical == "contractcredit"
    assert result.calculation.output_value == "5000.00"
    assert result.finding.state == "READY_FOR_REVIEW"
    assert result.calculation.formula_id != "aviation_mr_unreimbursed_balance"


def test_vertical_consumers_reject_invalid_economics_fail_closed():
    context = TenantContext("tenant", "analyst", ("analyst",))
    with pytest.raises(AssuranceKernelError):
        AviationLeaseRecoveryConsumer().evaluate(
            context=context,
            contract_ref="lease",
            event_ref="event",
            eligible_cost=Decimal("-1"),
            reimbursed_amount=Decimal("0"),
            notice_due=date(2026, 9, 1),
        )
    with pytest.raises(AssuranceKernelError):
        ContractCreditRecoveryConsumer().evaluate(
            context=context,
            contract_ref="msa",
            incident_ref="incident",
            monthly_fee=Decimal("100"),
            credit_rate=Decimal("1.1"),
            notice_due=date(2026, 9, 1),
        )


def test_vertical_consumers_require_tenant_role():
    context = TenantContext("tenant", "actor", ())
    with pytest.raises(Exception):
        AviationLeaseRecoveryConsumer().evaluate(
            context=context,
            contract_ref="lease",
            event_ref="event",
            eligible_cost=Decimal("1"),
            reimbursed_amount=Decimal("0"),
            notice_due=date(2026, 9, 1),
        )
