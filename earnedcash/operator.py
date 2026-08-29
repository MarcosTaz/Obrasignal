from __future__ import annotations

from decimal import Decimal

from .recovery_queue import RecoveryQueueItem
from .service import PayloadError, reconcile_operator_verified_payload
from .store import EarnedCashStore


class AssistedPilotOperator:
    """Trusted assisted-pilot boundary for evidence-reviewed project truth.

    This class is intentionally not registered as an HTTP endpoint. The caller is
    responsible for completing the human evidence review described in the pilot
    runbook before supplying `verified` / `due` truth fields.
    """

    def __init__(self, store: EarnedCashStore):
        self.store = store

    def reconcile_project(
        self,
        *,
        tenant_id: str,
        project_id: str,
        rows: object,
    ) -> dict:
        if not isinstance(rows, list):
            raise PayloadError("records_array_required")
        if any(
            not isinstance(row, dict)
            or str(row.get("project_id") or "").strip() != project_id
            for row in rows
        ):
            raise PayloadError("operator_project_scope_mismatch")

        result = reconcile_operator_verified_payload(rows, tenant_id=tenant_id)
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
        return result
