from datetime import date
from decimal import Decimal
import sqlite3

from earnedcash.attribution import verified_case_cash_attribution
from earnedcash.backup import copy_database, restore_verified_copy
from earnedcash.case_workflow import CaseState
from earnedcash.cash_verification import CashEvidence, CashEvidenceKind
from earnedcash.due_date import DueDateEvidence
from earnedcash.fees import calculate_success_fee
from earnedcash.operator import AssistedPilotOperator
from earnedcash.store import EarnedCashStore


AS_OF = date(2026, 8, 29)


def ledger():
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
        },
    ]


def due_evidence(due_date):
    return {
        "inv-1": DueDateEvidence(
            due_date=due_date,
            evidence_ref="invoice:inv-1:due-date",
            independently_verified=True,
        )
    }


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


def test_synthetic_pilot_reconciles_to_attributed_cash_fee_and_restorable_truth():
    store = pilot_store()
    operator = AssistedPilotOperator(store)
    result = operator.reconcile_project(
        tenant_id="tenant-1",
        project_id="project-1",
        rows=ledger(),
        as_of=AS_OF,
        due_evidence_by_record=due_evidence(AS_OF),
    )
    assert result["truth_source"] == "ASSISTED_OPERATOR_VERIFIED"
    assert result["as_of"] == "2026-08-29"
    assert result["due_truth"]["inv-1"]["state"] == "DUE"
    assert result["due_unpaid"] == "100000"
    assert result["verified_cash"] == "0"
    assert result["unknown_value"] == "0"
    assert len(result["recovery_queue"]) == 1
    assert result["queue_persisted"] is True

    case_id = result["recovery_queue"][0]["case_id"]
    assert store.list_cases(
        tenant_id="tenant-1", project_id="project-1"
    )[0]["case_id"] == case_id

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

    project_cash = store.verified_cash_total(
        tenant_id="tenant-1", project_id="project-1"
    )
    assert project_cash == Decimal("100000")
    assert store.list_cases(
        tenant_id="tenant-1", project_id="project-1"
    )[0]["status"] == "PAID"
    assert store.audit_valid("tenant-1") is True

    attribution = verified_case_cash_attribution(
        store, tenant_id="tenant-1", project_id="project-1"
    )
    assert attribution.valid is True
    assert attribution.verified_total == Decimal("100000")
    assert attribution.attributions[0].case_id == case_id
    assert attribution.attributions[0].evidence_ref == "bank:synthetic-tx-1"

    fee = calculate_success_fee(
        verified_cash_received=attribution.verified_total,
        fee_rate=Decimal("0.15"),
        attribution_verified=attribution.valid,
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
    restored_attribution = verified_case_cash_attribution(
        restored, tenant_id="tenant-1", project_id="project-1"
    )
    assert restored_attribution.valid is True
    assert restored_attribution.verified_total == Decimal("100000")
    assert restored.list_cases(
        tenant_id="tenant-1", project_id="project-1"
    )[0]["status"] == "PAID"


def test_synthetic_zero_recovery_is_pass_and_creates_no_recovery_fee():
    store = pilot_store()
    operator = AssistedPilotOperator(store)
    result = operator.reconcile_project(
        tenant_id="tenant-1",
        project_id="project-1",
        rows=ledger(),
        as_of=AS_OF,
        due_evidence_by_record=due_evidence(date(2026, 8, 30)),
    )
    assert result["due_truth"]["inv-1"]["state"] == "NOT_YET_DUE"
    assert result["due_unpaid"] == "0"
    assert result["not_yet_due"] == "100000"
    assert result["recovery_queue"] == []
    assert store.list_cases(tenant_id="tenant-1", project_id="project-1") == []

    attribution = verified_case_cash_attribution(
        store, tenant_id="tenant-1", project_id="project-1"
    )
    assert attribution.valid is True
    assert attribution.verified_total == Decimal("0")
    fee = calculate_success_fee(
        verified_cash_received=attribution.verified_total,
        fee_rate=Decimal("0.15"),
        attribution_verified=attribution.valid,
    )
    assert fee.fee_due == Decimal("0.00")
