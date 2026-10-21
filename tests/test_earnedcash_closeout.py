from datetime import date, timedelta
from decimal import Decimal

from earnedcash.closeout import (
    FinalAccountReview,
    RetentionReview,
    review_final_account_case,
    review_retention_case,
)
from earnedcash.due_date import DueDateEvidence


AS_OF = date(2026, 8, 29)


def due_evidence(due_date=AS_OF, *, verified=True, ref="due:evidence"):
    return DueDateEvidence(
        due_date=due_date,
        evidence_ref=ref,
        independently_verified=verified,
    )


def retention(**overrides):
    values = dict(
        retention_id="ret-1",
        currency="GBP",
        amount_withheld=Decimal("50000"),
        valid_defects_open=False,
        closeout_complete=True,
        release_due_evidence=due_evidence(ref="ret:due"),
        release_condition_evidence_ref="ret:condition",
        defect_status_evidence_ref="ret:defects-clear",
        closeout_evidence_ref="ret:closeout",
    )
    values.update(overrides)
    return RetentionReview(**values)


def final_account(**overrides):
    values = dict(
        final_account_id="fa-1",
        currency="GBP",
        contractor_position=Decimal("120000"),
        customer_position=Decimal("120000"),
        agreed_value=Decimal("120000"),
        invoiced_against_final=Decimal("120000"),
        paid_against_final=Decimal("100000"),
        due_evidence=due_evidence(ref="fa:due"),
        agreement_evidence_ref="fa:agreement",
        invoice_evidence_ref="fa:invoice",
    )
    values.update(overrides)
    return FinalAccountReview(**values)


def test_matured_retention_with_full_lineage_enters_queue():
    reviewed, result = review_retention_case(
        tenant_id="t1", project_id="p1", as_of=AS_OF, review=retention()
    )
    assert result.potentially_recoverable == Decimal("50000")
    assert reviewed.state == "MATURED_EVIDENCE_SUPPORTED"
    assert reviewed.verified_cash == Decimal("0")
    assert reviewed.queue_item is not None
    assert reviewed.queue_item.category == "RETENTION_MATURED_UNRELEASED"
    assert reviewed.queue_item.evidence_chain == (
        "ret:due", "ret:condition", "ret:defects-clear", "ret:closeout"
    )


def test_retention_not_yet_due_never_enters_queue():
    reviewed, _ = review_retention_case(
        tenant_id="t1",
        project_id="p1",
        as_of=AS_OF,
        review=retention(
            release_due_evidence=due_evidence(
                AS_OF + timedelta(days=1), ref="ret:future-due"
            )
        ),
    )
    assert reviewed.state == "NOT_YET_DUE"
    assert reviewed.potentially_recoverable == Decimal("0")
    assert reviewed.queue_item is None


def test_retention_clean_defect_state_without_evidence_fails_closed():
    reviewed, _ = review_retention_case(
        tenant_id="t1",
        project_id="p1",
        as_of=AS_OF,
        review=retention(defect_status_evidence_ref=None),
    )
    assert reviewed.state == "UNKNOWN"
    assert reviewed.blocker == "DEFECT_STATE_UNKNOWN"
    assert reviewed.queue_item is None


def test_retention_release_stated_does_not_become_verified_cash_here():
    reviewed, result = review_retention_case(
        tenant_id="t1",
        project_id="p1",
        as_of=AS_OF,
        review=retention(amount_released=Decimal("10000")),
    )
    assert result.held_balance == Decimal("40000")
    assert reviewed.potentially_recoverable == Decimal("40000")
    assert reviewed.verified_cash == Decimal("0")


def test_agreed_due_final_account_with_lineage_enters_queue_net_of_paid():
    reviewed, result = review_final_account_case(
        tenant_id="t1", project_id="p1", as_of=AS_OF, review=final_account()
    )
    assert result.open_balance == Decimal("20000")
    assert result.potentially_recoverable == Decimal("20000")
    assert reviewed.verified_cash == Decimal("0")
    assert reviewed.queue_item is not None
    assert reviewed.queue_item.category == "FINAL_ACCOUNT_AGREED_UNPAID"
    assert reviewed.queue_item.evidence_chain == (
        "fa:due", "fa:agreement", "fa:invoice"
    )


def test_final_account_missing_agreement_evidence_is_unknown_and_not_queued():
    reviewed, _ = review_final_account_case(
        tenant_id="t1",
        project_id="p1",
        as_of=AS_OF,
        review=final_account(agreement_evidence_ref=None),
    )
    assert reviewed.state == "UNKNOWN"
    assert reviewed.blocker == "AGREEMENT_EVIDENCE_MISSING"
    assert reviewed.queue_item is None


def test_final_account_unknown_due_date_is_not_queued():
    reviewed, _ = review_final_account_case(
        tenant_id="t1",
        project_id="p1",
        as_of=AS_OF,
        review=final_account(
            due_evidence=DueDateEvidence(None, None, False)
        ),
    )
    assert reviewed.state == "UNKNOWN"
    assert reviewed.blocker == "DUE_DATE_UNKNOWN"
    assert reviewed.queue_item is None


def test_final_account_dispute_and_valid_deduction_reduce_queue_value():
    reviewed, result = review_final_account_case(
        tenant_id="t1",
        project_id="p1",
        as_of=AS_OF,
        review=final_account(
            paid_against_final=Decimal("80000"),
            disputed_value=Decimal("5000"),
            valid_deductions=Decimal("7000"),
        ),
    )
    assert result.open_balance == Decimal("28000")
    assert reviewed.queue_item is not None
    assert reviewed.queue_item.amount == Decimal("28000")
