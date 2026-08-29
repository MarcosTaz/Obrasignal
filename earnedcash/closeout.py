from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .due_date import DueDateEvidence, DueTruthResult, determine_due_truth
from .final_account import (
    FinalAccountInput,
    FinalAccountResult,
    FinalAccountState,
    evaluate_final_account,
)
from .recovery_queue import RecoveryQueueItem
from .retention import RetentionInput, RetentionResult, RetentionState, evaluate_retention


ZERO = Decimal("0")


def _ref(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _score(amount: Decimal) -> int:
    if amount >= Decimal("100000"):
        return 90
    if amount >= Decimal("50000"):
        return 80
    if amount >= Decimal("10000"):
        return 70
    if amount > ZERO:
        return 60
    return 0


@dataclass(frozen=True)
class RetentionReview:
    retention_id: str
    currency: str
    amount_withheld: Decimal
    amount_released: Decimal = ZERO
    valid_defects_open: bool | None = None
    closeout_complete: bool | None = None
    release_due_evidence: DueDateEvidence = DueDateEvidence(None, None, False)
    release_condition_evidence_ref: str | None = None
    defect_status_evidence_ref: str | None = None
    closeout_evidence_ref: str | None = None
    overlap_reviewed: bool = False
    overlapping_case_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class FinalAccountReview:
    final_account_id: str
    currency: str
    contractor_position: Decimal | None
    customer_position: Decimal | None
    agreed_value: Decimal | None
    invoiced_against_final: Decimal | None
    paid_against_final: Decimal | None
    valid_deductions: Decimal = ZERO
    disputed_value: Decimal = ZERO
    due_evidence: DueDateEvidence = DueDateEvidence(None, None, False)
    agreement_evidence_ref: str | None = None
    invoice_evidence_ref: str | None = None
    overlap_reviewed: bool = False
    overlapping_case_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewedCloseoutCase:
    queue_item: RecoveryQueueItem | None
    state: str
    blocker: str | None
    due_truth: DueTruthResult
    potentially_recoverable: Decimal
    verified_cash: Decimal


def review_retention_case(
    *,
    tenant_id: str,
    project_id: str,
    as_of: date,
    review: RetentionReview,
) -> tuple[ReviewedCloseoutCase, RetentionResult]:
    due_truth = determine_due_truth(as_of=as_of, evidence=review.release_due_evidence)
    release_ref = _ref(review.release_condition_evidence_ref)
    defects_ref = _ref(review.defect_status_evidence_ref)
    closeout_ref = _ref(review.closeout_evidence_ref)

    defects_state = review.valid_defects_open if defects_ref else None
    closeout_state = review.closeout_complete if closeout_ref else None
    result = evaluate_retention(
        RetentionInput(
            tenant_id=tenant_id,
            project_id=project_id,
            currency=review.currency.upper(),
            amount_withheld=review.amount_withheld,
            amount_released=review.amount_released,
            release_due=due_truth.due,
            valid_defects_open=defects_state,
            closeout_complete=closeout_state,
            release_condition_evidence_verified=release_ref is not None,
            payment_evidence_verified=False,
        )
    )

    queue_item = None
    evidence_chain = tuple(
        ref
        for ref in (
            due_truth.evidence_ref,
            release_ref,
            defects_ref,
            closeout_ref,
        )
        if ref
    )
    if (
        result.state == RetentionState.MATURED_EVIDENCE_SUPPORTED
        and result.potentially_recoverable > ZERO
        and len(evidence_chain) == 4
    ):
        queue_item = RecoveryQueueItem(
            case_id=f"retention:{review.retention_id}",
            category="RETENTION_MATURED_UNRELEASED",
            amount=result.potentially_recoverable,
            currency=review.currency.upper(),
            confidence="HIGH",
            evidence_quality="HIGH",
            blocker="PAYMENT_DELAY",
            action="PREPARE_RETENTION_RELEASE_PACKAGE",
            priority_score=_score(result.potentially_recoverable),
            evidence_chain=evidence_chain,
        )

    return (
        ReviewedCloseoutCase(
            queue_item=queue_item,
            state=result.state.value,
            blocker=result.blocker,
            due_truth=due_truth,
            potentially_recoverable=result.potentially_recoverable,
            verified_cash=ZERO,
        ),
        result,
    )


def review_final_account_case(
    *,
    tenant_id: str,
    project_id: str,
    as_of: date,
    review: FinalAccountReview,
) -> tuple[ReviewedCloseoutCase, FinalAccountResult]:
    due_truth = determine_due_truth(as_of=as_of, evidence=review.due_evidence)
    agreement_ref = _ref(review.agreement_evidence_ref)
    invoice_ref = _ref(review.invoice_evidence_ref)
    result = evaluate_final_account(
        FinalAccountInput(
            tenant_id=tenant_id,
            project_id=project_id,
            currency=review.currency.upper(),
            contractor_position=review.contractor_position,
            customer_position=review.customer_position,
            agreed_value=review.agreed_value,
            invoiced_against_final=review.invoiced_against_final,
            paid_against_final=review.paid_against_final,
            valid_deductions=review.valid_deductions,
            disputed_value=review.disputed_value,
            agreement_evidence_verified=agreement_ref is not None,
            invoice_evidence_verified=invoice_ref is not None,
            payment_evidence_verified=False,
            payment_due=due_truth.due,
        )
    )

    queue_item = None
    evidence_chain = tuple(
        ref for ref in (due_truth.evidence_ref, agreement_ref, invoice_ref) if ref
    )
    if (
        result.state == FinalAccountState.AGREED_DUE_UNPAID
        and result.potentially_recoverable > ZERO
        and len(evidence_chain) == 3
    ):
        queue_item = RecoveryQueueItem(
            case_id=f"final-account:{review.final_account_id}",
            category="FINAL_ACCOUNT_AGREED_UNPAID",
            amount=result.potentially_recoverable,
            currency=review.currency.upper(),
            confidence="HIGH",
            evidence_quality="HIGH",
            blocker="PAYMENT_DELAY",
            action="PREPARE_FINAL_ACCOUNT_PAYMENT_PACKAGE",
            priority_score=_score(result.potentially_recoverable),
            evidence_chain=evidence_chain,
        )

    return (
        ReviewedCloseoutCase(
            queue_item=queue_item,
            state=result.state.value,
            blocker=result.blocker,
            due_truth=due_truth,
            potentially_recoverable=result.potentially_recoverable,
            verified_cash=ZERO,
        ),
        result,
    )
