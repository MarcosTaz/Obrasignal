from decimal import Decimal

import pytest

from earnedcash.recovery_queue import RecoveryQueueItem
from earnedcash.store import EarnedCashStore


def seeded_store():
    store = EarnedCashStore.memory()
    store.create_company(tenant_id="t1", company_id="co1", name="Alpha Electrical")
    store.create_customer(
        tenant_id="t1", customer_id="cust1", company_id="co1", name="Main Contractor"
    )
    store.create_project(
        tenant_id="t1", project_id="p1", company_id="co1", customer_id="cust1",
        name="Hospital MEP", currency="GBP"
    )
    store.create_contract(
        tenant_id="t1", contract_id="ct1", project_id="p1",
        contract_ref="JCT-001", original_value="500000"
    )
    return store


def queue_item():
    return RecoveryQueueItem(
        case_id="invoice:inv1",
        category="INVOICED_DUE_UNPAID",
        amount=Decimal("25000"),
        currency="GBP",
        confidence="HIGH",
        evidence_quality="HIGH",
        blocker="PAYMENT_DELAY",
        action="PREPARE_PAYMENT_EVIDENCE_PACKAGE",
        priority_score=70,
        evidence_chain=("app1", "cert1", "inv1"),
    )


def test_company_customer_project_contract_create_a_valid_audit_chain():
    store = seeded_store()
    history = store.audit_history("t1")
    assert [event.event_type for event in history] == [
        "COMPANY_CREATED", "CUSTOMER_CREATED", "PROJECT_CREATED", "CONTRACT_CREATED"
    ]
    assert store.audit_valid("t1") is True


def test_cross_tenant_parent_reference_is_rejected():
    store = seeded_store()
    with pytest.raises(ValueError, match="company_not_found_for_tenant"):
        store.create_customer(
            tenant_id="t2", customer_id="x", company_id="co1", name="Leak Attempt"
        )


def test_recovery_queue_is_tenant_and_project_scoped():
    store = seeded_store()
    store.replace_recovery_queue(tenant_id="t1", project_id="p1", items=(queue_item(),))
    assert store.list_cases(tenant_id="t1", project_id="p1")[0]["amount"] == "25000"
    assert store.list_cases(tenant_id="t2", project_id="p1") == []
    assert store.audit_valid("t1") is True


def test_case_currency_mismatch_is_rejected():
    store = seeded_store()
    bad = RecoveryQueueItem(**{**queue_item().__dict__, "currency": "EUR"})
    with pytest.raises(ValueError, match="case_currency_mismatch"):
        store.replace_recovery_queue(tenant_id="t1", project_id="p1", items=(bad,))


def test_unverified_cash_cannot_be_recorded():
    store = seeded_store()
    with pytest.raises(ValueError, match="cash_requires_verified_evidence"):
        store.record_verified_cash(
            tenant_id="t1", project_id="p1", receipt_id="r1", amount="1000",
            currency="GBP", evidence_ref="bank:tx1", verified=False
        )
    assert store.verified_cash_total(tenant_id="t1", project_id="p1") == Decimal("0")


def test_verified_cash_requires_project_currency_and_evidence():
    store = seeded_store()
    with pytest.raises(ValueError, match="cash_currency_mismatch"):
        store.record_verified_cash(
            tenant_id="t1", project_id="p1", receipt_id="r1", amount="1000",
            currency="EUR", evidence_ref="bank:tx1", verified=True
        )
    with pytest.raises(ValueError, match="evidence_ref is required"):
        store.record_verified_cash(
            tenant_id="t1", project_id="p1", receipt_id="r1", amount="1000",
            currency="GBP", evidence_ref="", verified=True
        )


def test_verified_cash_is_tenant_scoped_and_audited():
    store = seeded_store()
    store.record_verified_cash(
        tenant_id="t1", project_id="p1", receipt_id="r1", amount="1000",
        currency="GBP", evidence_ref="bank:tx1", verified=True
    )
    assert store.verified_cash_total(tenant_id="t1", project_id="p1") == Decimal("1000")
    assert store.verified_cash_total(tenant_id="t2", project_id="p1") == Decimal("0")
    assert store.audit_history("t1")[-1].event_type == "VERIFIED_CASH_RECORDED"
    assert store.audit_valid("t1") is True


def test_audit_database_tamper_is_detected():
    store = seeded_store()
    store.connection.execute(
        "UPDATE earnedcash_audit_events SET payload_json=? WHERE tenant_id=? AND sequence=?",
        ('{"name":"Tampered"}', "t1", 1),
    )
    store.connection.commit()
    assert store.audit_valid("t1") is False
