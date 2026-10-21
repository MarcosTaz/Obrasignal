from datetime import date
from decimal import Decimal

import pytest

from factory_cloud.assurance_store import AssuranceStore, AssuranceStoreError
from factory_cloud.shared_platform import TenantContext
from factory_cloud.vertical_consumers import AviationLeaseRecoveryConsumer, ContractCreditRecoveryConsumer


def _persist(store, result):
    store.persist_case(
        evidence=result.evidence,
        calculation=result.calculation,
        deadline=result.deadline,
        finding=result.finding,
        audit=result.audit,
        notification=result.notification,
    )


def test_two_verticals_persist_in_isolated_tenants(tmp_path):
    store = AssuranceStore(tmp_path / "assurance.sqlite3")
    aviation = AviationLeaseRecoveryConsumer().evaluate(
        context=TenantContext("airline", "a1", ("analyst",)),
        contract_ref="lease",
        event_ref="event",
        eligible_cost=Decimal("100"),
        reimbursed_amount=Decimal("25"),
        notice_due=date(2026, 9, 30),
    )
    credit = ContractCreditRecoveryConsumer().evaluate(
        context=TenantContext("enterprise", "a2", ("analyst",)),
        contract_ref="msa",
        incident_ref="inc",
        monthly_fee=Decimal("1000"),
        credit_rate=Decimal("0.1"),
        notice_due=date(2026, 9, 15),
    )
    _persist(store, aviation)
    _persist(store, credit)
    assert store.count("evidence", "airline") == 2
    assert store.count("evidence", "enterprise") == 2
    assert store.count("findings", "airline") == 1
    assert store.count("findings", "enterprise") == 1
    assert store.count("notification_outbox", "airline") == 1
    assert store.count("notification_outbox", "enterprise") == 1


def test_case_replay_is_idempotent(tmp_path):
    store = AssuranceStore(tmp_path / "assurance.sqlite3")
    result = ContractCreditRecoveryConsumer().evaluate(
        context=TenantContext("enterprise", "a2", ("analyst",)),
        contract_ref="msa",
        incident_ref="inc",
        monthly_fee=Decimal("1000"),
        credit_rate=Decimal("0.1"),
        notice_due=date(2026, 9, 15),
    )
    _persist(store, result)
    _persist(store, result)
    assert store.count("evidence", "enterprise") == 2
    assert store.count("calculations", "enterprise") == 1
    assert store.count("audit_events", "enterprise") == 1
    assert store.count("notification_outbox", "enterprise") == 1


def test_cross_tenant_case_is_rejected_before_write(tmp_path):
    store = AssuranceStore(tmp_path / "assurance.sqlite3")
    aviation = AviationLeaseRecoveryConsumer().evaluate(
        context=TenantContext("airline", "a1", ("analyst",)),
        contract_ref="lease",
        event_ref="event",
        eligible_cost=Decimal("100"),
        reimbursed_amount=Decimal("25"),
        notice_due=date(2026, 9, 30),
    )
    credit = ContractCreditRecoveryConsumer().evaluate(
        context=TenantContext("enterprise", "a2", ("analyst",)),
        contract_ref="msa",
        incident_ref="inc",
        monthly_fee=Decimal("1000"),
        credit_rate=Decimal("0.1"),
        notice_due=date(2026, 9, 15),
    )
    with pytest.raises(AssuranceStoreError, match="cross-tenant"):
        store.persist_case(
            evidence=aviation.evidence,
            calculation=credit.calculation,
            deadline=aviation.deadline,
            finding=aviation.finding,
            audit=aviation.audit,
            notification=aviation.notification,
        )
    assert store.count("evidence", "airline") == 0
    assert store.count("evidence", "enterprise") == 0
