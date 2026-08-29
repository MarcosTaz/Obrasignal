from decimal import Decimal
import sqlite3

from earnedcash.backup import copy_database, restore_verified_copy
from earnedcash.case_workflow import CaseState
from earnedcash.cash_verification import CashEvidence, CashEvidenceKind
from earnedcash.fees import calculate_success_fee
from earnedcash.recovery_queue import RecoveryQueueItem
from earnedcash.service import reconcile_payload
from earnedcash.store import EarnedCashStore


def ledger(*, due=True):
    return [
        {
            "record_id": "app-1",
            "customer_id": "cust-1",
            "project_id": "project-1",
            "currency": "GBP",
            "kind": "APPLICATION",
            "amount": "100000",
            "verified": True,
        },
        {
            "record_id": "cert-1",
            "customer_id": "cust-1",
            "project_id": "project-1",
            "currency": "GBP",
            "kind": "CERTIFICATE",
            "amount": "100000",
            "relates_to": "app-1",
            "verified": True,
        },
        {
            "record_id": "inv-1",
            "customer_id": "cust-1",
            "project_id": "project-1",
            "currency": "GBP",
            "kind": "INVOICE",
            "amount": "100000",
            "relates_to": "cert-1",
            "verified": True,
            "due": due,
        },
    ]


def queue_from_result(result):
    return tuple(
        RecoveryQueueItem(
            case_id=item["case_id"],
            category=item["category"],
            amount=Decimal(item["amount"]),
            currency=item["currency"],
            confidence=item["confidence"],
            evidence_quality=item["evidence_quality"],
            blocker=item["blocker"],
            action=item["action"],
            priority_score=item["priority_score"],
            evidence_chain=tuple(item["evidence_chain"]),
        )
        for item in result["recovery_queue"]
    )


def pilot_store():
    store = EarnedCashStore.memory()
    store.create_company(tenant_id="tenant-1", company_id="company-1", name="Synthetic MEP")
    store.create_customer(
        tenant_id="tenant-1",
        customer_id="cust-1",
        company_id="company-1",
        name="Synthetic Main Contractor",
    )
    store.create_project(
        tenant_id="tenant-1",
        project_id="project-1",
        company_id="company-1",
        customer_id="cust-1",
        name="Synthetic Hospital MEP",
        currency="GBP",
    )
    store.create_contract(
        tenant_id="tenant-1",
        contract_id="contract-1",
        project_id="project-1",
        contract_ref="SYN-JCT-001",
        original_value="750000",
    )
    return store


def test_synthetic_pilot_reconciles_to_verified_cash_fee_and_restorable_truth():
    result = reconcile_payload(ledger(due=True), tenant_id="tenant-1")
    assert result["due_unpaid"] == "100000"
    assert result["verified_cash"] == "0"
    assert result["unknown_value"] == "0"
    assert len(result["recovery_queue"]) == 1

    store = pilot_store()
    store.replace_recovery_queue(
        tenant_id="tenant-1",
        project_id="project-1",
        items=queue_from_result(result),
    )
    case_id = result["recovery_queue"][0]["case_id"]

    store.transition_case(
        tenant_id="tenant-1",
        project_id="project-1",
        case_id=case_id,
        target=CaseState.ACTION_APPROVED,
        customer_approved=True,
    )
    store.transition_case(
        tenant_id="tenant-1",
        project_id="project-1",
        case_id=case_id,
        target=CaseState.RECOVERY_REQUESTED,
        customer_approved=True,
    )
    store.transition_case(
        tenant_id="tenant-1",
        project_id="project-1",
        case_id=case_id,
        target=CaseState.PAID,
        receipt_id="receipt-1",
        cash_evidence=CashEvidence(
            evidence_ref="bank:synthetic-tx-1",
            kind=CashEvidenceKind.BANK_RECEIPT,
            tenant_id="tenant-1",
            project_id="project-1",
            currency="GBP",
            amount=Decimal("100000"),
            independently_verified=True,
        ),
    )

    verified_cash = store.verified_cash_total(
        tenant_id="tenant-1", project_id="project-1"
    )
    assert verified_cash == Decimal("100000")
    assert store.list_cases(
        tenant_id="tenant-1", project_id="project-1"
    )[0]["status"] == "PAID"
    assert store.audit_valid("tenant-1") is True

    fee = calculate_success_fee(
        verified_cash_received=verified_cash,
        fee_rate=Decimal("0.15"),
        attribution_verified=True,
    )
    assert fee.verified_economic_result == Decimal("100000")
    assert fee.fee_due == Decimal("15000.00")

    backup = sqlite3.connect(":memory:")
    copied_fingerprint = copy_database(store.connection, backup)
    restored_connection = sqlite3.connect(":memory:")
    restored_fingerprint = restore_verified_copy(
        backup, restored_connection, tenant_ids=("tenant-1",)
    )
    assert restored_fingerprint == copied_fingerprint

    restored = EarnedCashStore(restored_connection)
    assert restored.verified_cash_total(
        tenant_id="tenant-1", project_id="project-1"
    ) == Decimal("100000")
    assert restored.list_cases(
        tenant_id="tenant-1", project_id="project-1"
    )[0]["status"] == "PAID"


def test_synthetic_zero_recovery_is_pass_and_creates_no_recovery_fee():
    result = reconcile_payload(ledger(due=False), tenant_id="tenant-1")
    assert result["due_unpaid"] == "0"
    assert result["not_yet_due"] == "100000"
    assert result["recovery_queue"] == []

    fee = calculate_success_fee(
        verified_cash_received=Decimal("0"),
        fee_rate=Decimal("0.15"),
        attribution_verified=True,
    )
    assert fee.fee_due == Decimal("0.00")
