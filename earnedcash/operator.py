from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from .due_date import DueDateEvidence, determine_due_truth
from .recovery_queue import RecoveryQueueItem
from .service import PayloadError, reconcile_operator_verified_payload
from .store import EarnedCashStore


class AssistedPilotOperator:
    """Trusted assisted-pilot boundary for evidence-reviewed project truth.

    This class is intentionally not registered as an HTTP endpoint. `verified`
    fields represent completed human evidence review. Invoice due-state is not
    accepted as a magic boolean: it is derived deterministically from explicit
    `as_of` and independently verified due-date evidence.
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

        result = reconcile_operator_verified_payload(
            reviewed_rows, tenant_id=tenant_id
        )
        queue = tuple(
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
        self.store.replace_recovery_queue(
            tenant_id=tenant_id,
            project_id=project_id,
            items=queue,
        )
        result = dict(result)
        result["queue_persisted"] = True
        result["truth_source"] = "ASSISTED_OPERATOR_VERIFIED"
        result["as_of"] = as_of.isoformat()
        result["due_truth"] = due_truth
        return result
