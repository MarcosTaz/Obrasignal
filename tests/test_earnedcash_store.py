from decimal import Decimal
import sqlite3

import pytest

from earnedcash.case_workflow import CaseState
from earnedcash.cash_verification import CashEvidence, CashEvidenceKind
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


def queue_item(case_id="invoice:inv1", amount="25000"):
    return RecoveryQueueItem(
        case_id=case_id,
        category="INVOICED_DUE_UNPAID",
        amount=Decimal(amount),
        currency="GBP",
        confidence="HIGH",
        evidence_quality="HIGH",
        blocker="PAYMENT_DELAY",
        action="PREPARE_PAYMENT_EVIDENCE_PACKAGE",
        priority_score=70,
        evidence_chain=("app1", "cert1", case_id.split(":", 1)[-1]),
    )


def cash_evidence(
    *,
    evidence_ref="bank:tx1",
    tenant_id="t1",
    project_id="p1",
    currency="GBP",
    amount="1000",
    independently_verified=True,
):
    return CashEvidence(
        evidence_ref=evidence_ref,
        kind=CashEvidenceKind.BANK_RECEIPT,
        tenant_id=tenant_id,
        project_id=project_id,
        currency=currency,
        amount=Decimal(amount),
        independently_verified=independently_verified,
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


def test_customer_cannot_be_attached_to_another_company():
    store = seeded_store()
    store.create_company(tenant_id="t1", company_id="co2", name="Beta Mechanical")
    with pytest.raises(ValueError, match="customer_company_mismatch"):
        store.create_project(
            tenant_id="t1",
            project_id="p2",
            company_id="co2",
            customer_id="cust1",
            name="Cross-company leak attempt",
            currency="GBP",
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
    with pytest.raises(ValueError, match="EVIDENCE_NOT_INDEPENDENTLY_VERIFIED"):
        store.record_verified_cash(
            tenant_id="t1",
            project_id="p1",
            receipt_id="r1",
            amount="1000",
            currency="GBP",
            evidence=cash_evidence(independently_verified=False),
        )
    assert store.verified_cash_total(tenant_id="t1", project_id="p1") == Decimal("0")


def test_verified_cash_requires_project_currency_and_evidence():
    store = seeded_store()
    with pytest.raises(ValueError, match="cash_currency_mismatch"):
        store.record_verified_cash(
            tenant_id="t1",
            project_id="p1",
            receipt_id="r1",
            amount="1000",
            currency="EUR",
            evidence=cash_evidence(currency="EUR"),
        )
    with pytest.raises(ValueError, match="EVIDENCE_REFERENCE_MISSING"):
        store.record_verified_cash(
            tenant_id="t1",
            project_id="p1",
            receipt_id="r1",
            amount="1000",
            currency="GBP",
            evidence=cash_evidence(evidence_ref=""),
        )


def test_verified_cash_is_tenant_scoped_and_audited():
    store = seeded_store()
    store.record_verified_cash(
        tenant_id="t1",
        project_id="p1",
        receipt_id="r1",
        amount="1000",
        currency="GBP",
        evidence=cash_evidence(),
    )
    assert store.verified_cash_total(tenant_id="t1", project_id="p1") == Decimal("1000")
    assert store.verified_cash_total(tenant_id="t2", project_id="p1") == Decimal("0")
    assert store.audit_history("t1")[-1].event_type == "VERIFIED_CASH_RECORDED"
    assert store.audit_valid("t1") is True


def test_same_cash_evidence_cannot_be_counted_twice():
    store = seeded_store()
    evidence = cash_evidence(evidence_ref="bank:unique-1")
    store.record_verified_cash(
        tenant_id="t1",
        project_id="p1",
        receipt_id="r1",
        amount="1000",
        currency="GBP",
        evidence=evidence,
    )
    with pytest.raises(sqlite3.IntegrityError):
        store.record_verified_cash(
            tenant_id="t1",
            project_id="p1",
            receipt_id="r2",
            amount="1000",
            currency="GBP",
            evidence=evidence,
        )
    assert store.verified_cash_total(tenant_id="t1", project_id="p1") == Decimal("1000")


def test_case_transition_is_persisted_only_after_required_gates():
    store = seeded_store()
    store.replace_recovery_queue(
        tenant_id="t1", project_id="p1", items=(queue_item(amount="1000"),)
    )
    with pytest.raises(ValueError, match="customer approval required"):
        store.transition_case(
            tenant_id="t1",
            project_id="p1",
            case_id="invoice:inv1",
            target=CaseState.ACTION_APPROVED,
        )
    assert store.list_cases(tenant_id="t1", project_id="p1")[0]["status"] == "OPEN"

    store.transition_case(
        tenant_id="t1",
        project_id="p1",
        case_id="invoice:inv1",
        target=CaseState.ACTION_APPROVED,
        customer_approved=True,
    )
    store.transition_case(
        tenant_id="t1",
        project_id="p1",
        case_id="invoice:inv1",
        target=CaseState.RECOVERY_REQUESTED,
        customer_approved=True,
    )
    assert store.list_cases(tenant_id="t1", project_id="p1")[0]["status"] == "RECOVERY_REQUESTED"


def test_paid_transition_records_exact_scope_cash_once():
    store = seeded_store()
    store.replace_recovery_queue(
        tenant_id="t1", project_id="p1", items=(queue_item(amount="1000"),)
    )
    store.transition_case(
        tenant_id="t1",
        project_id="p1",
        case_id="invoice:inv1",
        target=CaseState.ACTION_APPROVED,
        customer_approved=True,
    )
    store.transition_case(
        tenant_id="t1",
        project_id="p1",
        case_id="invoice:inv1",
        target=CaseState.RECOVERY_REQUESTED,
        customer_approved=True,
    )
    store.transition_case(
        tenant_id="t1",
        project_id="p1",
        case_id="invoice:inv1",
        target=CaseState.PAID,
        receipt_id="r1",
        cash_evidence=cash_evidence(amount="1000"),
    )
    assert store.list_cases(tenant_id="t1", project_id="p1")[0]["status"] == "PAID"
    assert store.verified_cash_total(tenant_id="t1", project_id="p1") == Decimal("1000")
    assert store.audit_valid("t1") is True


def test_audit_database_tamper_is_detected():
    store = seeded_store()
    store.connection.execute(
        "UPDATE earnedcash_audit_events SET payload_json=? WHERE tenant_id=? AND sequence=?",
        ('{"name":"Tampered"}', "t1", 1),
    )
    store.connection.commit()
    assert store.audit_valid("t1") is False
