from decimal import Decimal

from earnedcash.attribution import verified_case_cash_attribution
from earnedcash.case_workflow import CaseState
from earnedcash.cash_verification import CashEvidence, CashEvidenceKind
from earnedcash.recovery_queue import RecoveryQueueItem
from earnedcash.store import EarnedCashStore


def cash_evidence(ref, amount="1000"):
    return CashEvidence(
        evidence_ref=ref,
        kind=CashEvidenceKind.BANK_RECEIPT,
        tenant_id="t1",
        project_id="p1",
        currency="GBP",
        amount=Decimal(amount),
        independently_verified=True,
    )


def store_with_case():
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
    return store


def approve_request_and_pay(store):
    store.transition_case(
        tenant_id="t1", project_id="p1", case_id="invoice:inv1",
        target=CaseState.ACTION_APPROVED, customer_approved=True,
    )
    store.transition_case(
        tenant_id="t1", project_id="p1", case_id="invoice:inv1",
        target=CaseState.RECOVERY_REQUESTED, customer_approved=True,
    )
    store.transition_case(
        tenant_id="t1", project_id="p1", case_id="invoice:inv1",
        target=CaseState.PAID, receipt_id="receipt-case",
        cash_evidence=cash_evidence("bank:case"),
    )


def test_paid_case_cash_is_exactly_attributed():
    store = store_with_case()
    approve_request_and_pay(store)
    result = verified_case_cash_attribution(store, tenant_id="t1", project_id="p1")
    assert result.valid is True
    assert result.issues == ()
    assert result.verified_total == Decimal("1000")
    assert len(result.attributions) == 1
    attribution = result.attributions[0]
    assert attribution.case_id == "invoice:inv1"
    assert attribution.receipt_id == "receipt-case"
    assert attribution.evidence_ref == "bank:case"


def test_unattributed_project_cash_is_excluded_from_fee_base():
    store = store_with_case()
    store.record_verified_cash(
        tenant_id="t1",
        project_id="p1",
        receipt_id="receipt-project",
        amount="400",
        currency="GBP",
        evidence=cash_evidence("bank:project", amount="400"),
    )
    assert store.verified_cash_total(tenant_id="t1", project_id="p1") == Decimal("400")
    result = verified_case_cash_attribution(store, tenant_id="t1", project_id="p1")
    assert result.valid is True
    assert result.verified_total == Decimal("0")
    assert result.attributions == ()


def test_project_cash_plus_paid_case_only_attributes_paid_case_amount():
    store = store_with_case()
    store.record_verified_cash(
        tenant_id="t1",
        project_id="p1",
        receipt_id="receipt-unrelated",
        amount="400",
        currency="GBP",
        evidence=cash_evidence("bank:unrelated", amount="400"),
    )
    approve_request_and_pay(store)
    assert store.verified_cash_total(tenant_id="t1", project_id="p1") == Decimal("1400")
    result = verified_case_cash_attribution(store, tenant_id="t1", project_id="p1")
    assert result.valid is True
    assert result.verified_total == Decimal("1000")


def test_tampered_audit_chain_fails_attribution_closed_to_zero():
    store = store_with_case()
    approve_request_and_pay(store)
    store.connection.execute(
        "UPDATE earnedcash_audit_events SET payload_json=? WHERE tenant_id=? AND sequence=?",
        ('{"tampered":true}', "t1", 1),
    )
    store.connection.commit()
    result = verified_case_cash_attribution(store, tenant_id="t1", project_id="p1")
    assert result.valid is False
    assert result.verified_total == Decimal("0")
    assert result.issues == ("AUDIT_CHAIN_INVALID",)
