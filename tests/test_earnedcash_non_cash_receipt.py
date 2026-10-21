from decimal import Decimal

import pytest

from earnedcash.case_workflow import CaseState
from earnedcash.cash_verification import CashEvidence, CashEvidenceKind
from earnedcash.recovery_queue import RecoveryQueueItem
from earnedcash.store import EarnedCashStore


def store_with_requested_case():
    store = EarnedCashStore.memory()
    store.create_company(tenant_id="t1", company_id="co1", name="Alpha")
    store.create_customer(
        tenant_id="t1", customer_id="cust1", company_id="co1", name="Main"
    )
    store.create_project(
        tenant_id="t1", project_id="p1", company_id="co1", customer_id="cust1",
        name="Hospital", currency="GBP"
    )
    store.replace_recovery_queue(
        tenant_id="t1",
        project_id="p1",
        items=(
            RecoveryQueueItem(
                case_id="invoice:inv1",
                category="INVOICED_DUE_UNPAID",
                amount=Decimal("1000"),
                currency="GBP",
                confidence="HIGH",
                evidence_quality="HIGH",
                blocker="PAYMENT_DELAY",
                action="PREPARE_PAYMENT_EVIDENCE_PACKAGE",
                priority_score=70,
                evidence_chain=("app1", "cert1", "inv1"),
            ),
        ),
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
    return store


def credit_note():
    return CashEvidence(
        evidence_ref="credit:cn-1",
        kind=CashEvidenceKind.CREDIT_NOTE,
        tenant_id="t1",
        project_id="p1",
        currency="GBP",
        amount=Decimal("1000"),
        independently_verified=True,
    )


def test_credit_note_cannot_be_recorded_as_verified_cash():
    store = store_with_requested_case()
    with pytest.raises(ValueError, match="NON_CASH_EVIDENCE_KIND"):
        store.record_verified_cash(
            tenant_id="t1",
            project_id="p1",
            receipt_id="r-credit",
            amount="1000",
            currency="GBP",
            evidence=credit_note(),
        )
    assert store.verified_cash_total(tenant_id="t1", project_id="p1") == Decimal("0")


def test_credit_note_paid_transition_rolls_back_case_state_and_cash():
    store = store_with_requested_case()
    before_events = len(store.audit_history("t1"))
    with pytest.raises(ValueError, match="NON_CASH_EVIDENCE_KIND"):
        store.transition_case(
            tenant_id="t1",
            project_id="p1",
            case_id="invoice:inv1",
            target=CaseState.PAID,
            receipt_id="r-credit",
            cash_evidence=credit_note(),
        )
    case = store.list_cases(tenant_id="t1", project_id="p1")[0]
    assert case["status"] == "RECOVERY_REQUESTED"
    assert store.verified_cash_total(tenant_id="t1", project_id="p1") == Decimal("0")
    assert len(store.audit_history("t1")) == before_events
    assert store.audit_valid("t1") is True
