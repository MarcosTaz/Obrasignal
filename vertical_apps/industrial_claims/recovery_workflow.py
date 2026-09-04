from __future__ import annotations

from datetime import date
from typing import Any

from vertical_apps.industrial_claims.dossier import AssistedRecoveryAssessment
from vertical_apps.industrial_claims.leakage_reconciliation import reconcile_recovery_ledger
from vertical_apps.industrial_claims.recovery_dossier import (
    build_certactum_recovery_dossier,
    render_certactum_recovery_dossier_markdown,
)
from vertical_apps.industrial_claims.recovery_reconciliation_store import (
    PersistedRecoveryReconciliation,
    RecoveryReconciliationStore,
    RecoveryReconciliationStoreError,
)
from vertical_apps.industrial_claims.service import IndustrialClaimsService


class CertactumRecoveryWorkflow:
    """Current-finding workflow from economic reconciliation to auditable dossier."""

    def __init__(self, service: IndustrialClaimsService):
        self.service = service
        self.reconciliations = RecoveryReconciliationStore(service.store.path)

    def _require_current(self, *, tenant_id: str, finding_id: str) -> None:
        self.service.read_model.get_finding(tenant_id=tenant_id, finding_id=finding_id)
        self.service.revision_store.require_current(tenant_id=tenant_id, finding_id=finding_id)

    @staticmethod
    def _rehydrate(record: PersistedRecoveryReconciliation):
        payload = record.snapshot
        required = {
            "documented_cost",
            "mitigation",
            "evidence_supported",
            "claimed",
            "approved",
            "settled",
            "currency",
            "reconciliation_hash",
        }
        if not required.issubset(payload):
            raise RecoveryReconciliationStoreError("persisted reconciliation is incomplete")
        snapshot = reconcile_recovery_ledger(
            documented_cost=payload["documented_cost"],
            mitigation=payload["mitigation"],
            evidence_supported=payload["evidence_supported"],
            claimed=payload["claimed"],
            approved=payload["approved"],
            settled=payload["settled"],
            currency=payload["currency"],
        )
        if snapshot.reconciliation_hash != record.reconciliation_hash:
            raise RecoveryReconciliationStoreError("persisted reconciliation hash verification failed")
        return snapshot

    def record_reconciliation(
        self,
        *,
        tenant_id: str,
        finding_id: str,
        actor_id: str,
        evidence_ref: str,
        documented_cost: object,
        mitigation: object = "0",
        evidence_supported: object = "0",
        claimed: object = "0",
        approved: object = "0",
        settled: object = "0",
        currency: object,
        reversal_reason: str | None = None,
    ) -> PersistedRecoveryReconciliation:
        self._require_current(tenant_id=tenant_id, finding_id=finding_id)
        snapshot = reconcile_recovery_ledger(
            documented_cost=documented_cost,
            mitigation=mitigation,
            evidence_supported=evidence_supported,
            claimed=claimed,
            approved=approved,
            settled=settled,
            currency=currency,
        )
        return self.reconciliations.append(
            tenant_id=tenant_id,
            finding_id=finding_id,
            snapshot=snapshot,
            actor_id=actor_id,
            evidence_ref=evidence_ref,
            reversal_reason=reversal_reason,
        )

    def latest_reconciliation(
        self, *, tenant_id: str, finding_id: str
    ) -> PersistedRecoveryReconciliation:
        self._require_current(tenant_id=tenant_id, finding_id=finding_id)
        record = self.reconciliations.latest(tenant_id=tenant_id, finding_id=finding_id)
        if record is None:
            raise RecoveryReconciliationStoreError("current finding has no persisted recovery reconciliation")
        self._rehydrate(record)
        return record

    def build_latest_dossier(
        self,
        *,
        tenant_id: str,
        finding_id: str,
        assessment: AssistedRecoveryAssessment,
        as_of_date: date | None = None,
    ) -> dict[str, Any]:
        record = self.latest_reconciliation(tenant_id=tenant_id, finding_id=finding_id)
        snapshot = self._rehydrate(record)
        dossier = build_certactum_recovery_dossier(
            self.service,
            tenant_id=tenant_id,
            finding_id=finding_id,
            assessment=assessment,
            reconciliation=snapshot,
            as_of_date=as_of_date,
        )
        dossier["recovery_reconciliation_persistence"] = {
            "sequence": record.sequence,
            "reconciliation_hash": record.reconciliation_hash,
            "actor_id": record.actor_id,
            "evidence_ref": record.evidence_ref,
            "reversal_reason": record.reversal_reason,
            "created_at": record.created_at,
            "append_only_history": True,
        }
        return dossier

    def render_latest_dossier_markdown(
        self,
        *,
        tenant_id: str,
        finding_id: str,
        assessment: AssistedRecoveryAssessment,
        as_of_date: date | None = None,
    ) -> str:
        dossier = self.build_latest_dossier(
            tenant_id=tenant_id,
            finding_id=finding_id,
            assessment=assessment,
            as_of_date=as_of_date,
        )
        return render_certactum_recovery_dossier_markdown(dossier)
