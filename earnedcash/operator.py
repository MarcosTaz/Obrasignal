from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from .closeout import (
    FinalAccountReview,
    RetentionReview,
    review_final_account_case,
    review_retention_case,
)
from .due_date import DueDateEvidence, determine_due_truth
from .recovery_queue import RecoveryQueueItem
from .service import PayloadError, reconcile_operator_verified_payload
from .store import EarnedCashStore


ZERO = Decimal("0")


def _queue_item_from_dict(item: dict) -> RecoveryQueueItem:
    return RecoveryQueueItem(
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


def _queue_item_dict(item: RecoveryQueueItem) -> dict:
    return {
        "case_id": item.case_id,
        "category": item.category,
        "amount": str(item.amount),
        "currency": item.currency,
        "confidence": item.confidence,
        "evidence_quality": item.evidence_quality,
        "blocker": item.blocker,
        "action": item.action,
        "priority_score": item.priority_score,
        "evidence_chain": list(item.evidence_chain),
    }


def _review_truth(reviewed) -> dict:
    truth = reviewed.due_truth
    return {
        "state": reviewed.state,
        "blocker": reviewed.blocker,
        "potentially_recoverable": str(reviewed.potentially_recoverable),
        "verified_cash": str(reviewed.verified_cash),
        "due_truth": {
            "state": truth.state.value,
            "due": truth.due,
            "as_of": truth.as_of.isoformat(),
            "due_date": truth.due_date.isoformat() if truth.due_date else None,
            "evidence_ref": truth.evidence_ref,
            "reason": truth.reason,
        },
    }


class AssistedPilotOperator:
    """Trusted assisted-pilot boundary for evidence-reviewed project truth.

    This class is intentionally not registered as an HTTP endpoint. `verified`
    fields represent completed human evidence review. Invoice, retention and final
    account due-state are derived deterministically from explicit `as_of` and
    independently verified due-date evidence.
    """

    def __init__(self, store: EarnedCashStore):
        self.store = store

    def reconcile_project(
        self,
        *,
        tenant_id: str,
        project_id: str,
        rows: object,
        as_of: date,
        due_evidence_by_record: Mapping[str, DueDateEvidence] | None = None,
        retention_reviews: tuple[RetentionReview, ...] = (),
        final_account_reviews: tuple[FinalAccountReview, ...] = (),
    ) -> dict:
        if not isinstance(as_of, date):
            raise PayloadError("as_of_date_required")
        if not isinstance(rows, list):
            raise PayloadError("records_array_required")
        if any(
            not isinstance(row, dict)
            or str(row.get("project_id") or "").strip() != project_id
            for row in rows
        ):
            raise PayloadError("operator_project_scope_mismatch")

        due_evidence_by_record = due_evidence_by_record or {}
        reviewed_rows: list[dict] = []
        due_truth: dict[str, dict] = {}
        for index, source_row in enumerate(rows):
            row = dict(source_row)
            kind = str(row.get("kind") or "").strip().upper()
            if kind == "INVOICE":
                if "due" in row:
                    raise PayloadError("operator_due_boolean_forbidden")
                record_id = str(row.get("record_id") or "").strip()
                evidence = due_evidence_by_record.get(record_id) or DueDateEvidence(
                    due_date=None,
                    evidence_ref=None,
                    independently_verified=False,
                )
                truth = determine_due_truth(as_of=as_of, evidence=evidence)
                row["due"] = truth.due
                due_truth[record_id or f"row:{index}"] = {
                    "state": truth.state.value,
                    "due": truth.due,
                    "as_of": truth.as_of.isoformat(),
                    "due_date": truth.due_date.isoformat() if truth.due_date else None,
                    "evidence_ref": truth.evidence_ref,
                    "reason": truth.reason,
                }
            reviewed_rows.append(row)

        result = dict(
            reconcile_operator_verified_payload(reviewed_rows, tenant_id=tenant_id)
        )
        queue: list[RecoveryQueueItem] = [
            _queue_item_from_dict(item) for item in result["recovery_queue"]
        ]

        retention_truth: dict[str, dict] = {}
        for review in retention_reviews:
            reviewed, _ = review_retention_case(
                tenant_id=tenant_id,
                project_id=project_id,
                as_of=as_of,
                review=review,
            )
            retention_truth[review.retention_id] = _review_truth(reviewed)
            if reviewed.queue_item is not None:
                queue.append(reviewed.queue_item)

        final_account_truth: dict[str, dict] = {}
        for review in final_account_reviews:
            reviewed, _ = review_final_account_case(
                tenant_id=tenant_id,
                project_id=project_id,
                as_of=as_of,
                review=review,
            )
            final_account_truth[review.final_account_id] = _review_truth(reviewed)
            if reviewed.queue_item is not None:
                queue.append(reviewed.queue_item)

        queue.sort(
            key=lambda item: (-item.priority_score, -item.amount, item.case_id)
        )
        queue_tuple = tuple(queue)
        self.store.replace_recovery_queue(
            tenant_id=tenant_id,
            project_id=project_id,
            items=queue_tuple,
        )

        closeout_recoverable = sum(
            (
                Decimal(item["potentially_recoverable"])
                for item in (*retention_truth.values(), *final_account_truth.values())
            ),
            ZERO,
        )
        result["recovery_queue"] = [_queue_item_dict(item) for item in queue_tuple]
        result["queue_persisted"] = True
        result["truth_source"] = "ASSISTED_OPERATOR_VERIFIED"
        result["as_of"] = as_of.isoformat()
        result["due_truth"] = due_truth
        result["retention_truth"] = retention_truth
        result["final_account_truth"] = final_account_truth
        result["closeout_recoverable"] = str(closeout_recoverable)
        result["total_queue_value"] = str(
            sum((item.amount for item in queue_tuple), ZERO)
        )
        return result
