from datetime import date
from decimal import Decimal

from earnedcash.closeout import FinalAccountReview, RetentionReview
from earnedcash.due_date import DueDateEvidence
from earnedcash.operator import AssistedPilotOperator
from earnedcash.store import EarnedCashStore


AS_OF = date(2026, 8, 29)


def due(ref):
    return DueDateEvidence(
        due_date=AS_OF,
        evidence_ref=ref,
        independently_verified=True,
    )


def store():
    value = EarnedCashStore.memory()
    value.create_company(tenant_id="t1", company_id="co1", name="Alpha")
    value.create_customer(
        tenant_id="t1", customer_id="cust1", company_id="co1", name="Main"
    )
    value.create_project(
        tenant_id="t1", project_id="p1", company_id="co1", customer_id="cust1",
        name="Hospital", currency="GBP"
    )
    return value


def invoice_rows():
    return [
        {"record_id":"app1","customer_id":"cust1","project_id":"p1","currency":"GBP","kind":"APPLICATION","amount":"10000","verified":True},
        {"record_id":"cert1","customer_id":"cust1","project_id":"p1","currency":"GBP","kind":"CERTIFICATE","amount":"10000","relates_to":"app1","verified":True},
        {"record_id":"inv1","customer_id":"cust1","project_id":"p1","currency":"GBP","kind":"INVOICE","amount":"10000","relates_to":"cert1","verified":True},
    ]


def retention_review():
    return RetentionReview(
        retention_id="ret1",
        currency="GBP",
        amount_withheld=Decimal("5000"),
        valid_defects_open=False,
        closeout_complete=True,
        release_due_evidence=due("ret:due"),
        release_condition_evidence_ref="ret:condition",
        defect_status_evidence_ref="ret:defects-clear",
        closeout_evidence_ref="ret:closeout",
    )


def final_review():
    return FinalAccountReview(
        final_account_id="fa1",
        currency="GBP",
        contractor_position=Decimal("20000"),
        customer_position=Decimal("20000"),
        agreed_value=Decimal("20000"),
        invoiced_against_final=Decimal("20000"),
        paid_against_final=Decimal("13000"),
        due_evidence=due("fa:due"),
        agreement_evidence_ref="fa:agreement",
        invoice_evidence_ref="fa:invoice",
    )


def test_operator_composes_three_categories_without_collapsing_bucket_meaning():
    persistence = store()
    result = AssistedPilotOperator(persistence).reconcile_project(
        tenant_id="t1",
        project_id="p1",
        rows=invoice_rows(),
        as_of=AS_OF,
        due_evidence_by_record={"inv1": due("inv:due")},
        retention_reviews=(retention_review(),),
        final_account_reviews=(final_review(),),
    )

    assert result["due_unpaid"] == "10000"
    assert result["closeout_recoverable"] == "12000"
    assert result["total_queue_value"] == "22000"
    categories = {item["category"] for item in result["recovery_queue"]}
    assert categories == {
        "INVOICED_DUE_UNPAID",
        "RETENTION_MATURED_UNRELEASED",
        "FINAL_ACCOUNT_AGREED_UNPAID",
    }
    cases = persistence.list_cases(tenant_id="t1", project_id="p1")
    assert len(cases) == 3
    assert {case["category"] for case in cases} == categories
    assert persistence.audit_valid("t1") is True


def test_unknown_retention_or_final_account_never_enters_combined_queue():
    persistence = store()
    unknown_retention = RetentionReview(
        retention_id="ret-unknown",
        currency="GBP",
        amount_withheld=Decimal("5000"),
        valid_defects_open=False,
        closeout_complete=True,
        release_due_evidence=DueDateEvidence(None, None, False),
        release_condition_evidence_ref="ret:condition",
        defect_status_evidence_ref="ret:defects-clear",
        closeout_evidence_ref="ret:closeout",
    )
    unknown_final = FinalAccountReview(
        final_account_id="fa-unknown",
        currency="GBP",
        contractor_position=Decimal("20000"),
        customer_position=Decimal("20000"),
        agreed_value=Decimal("20000"),
        invoiced_against_final=Decimal("20000"),
        paid_against_final=Decimal("13000"),
        due_evidence=DueDateEvidence(None, None, False),
        agreement_evidence_ref="fa:agreement",
        invoice_evidence_ref="fa:invoice",
    )
    result = AssistedPilotOperator(persistence).reconcile_project(
        tenant_id="t1",
        project_id="p1",
        rows=[],
        as_of=AS_OF,
        retention_reviews=(unknown_retention,),
        final_account_reviews=(unknown_final,),
    )
    assert result["recovery_queue"] == []
    assert result["total_queue_value"] == "0"
    assert result["retention_truth"]["ret-unknown"]["state"] == "UNKNOWN"
    assert result["final_account_truth"]["fa-unknown"]["state"] == "UNKNOWN"
    assert persistence.list_cases(tenant_id="t1", project_id="p1") == []
