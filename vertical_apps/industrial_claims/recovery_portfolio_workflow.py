from __future__ import annotations

from dataclasses import dataclass

from vertical_apps.industrial_claims.recovery_portfolio import (
    PortfolioRecoveryRollup,
    RecoveryPortfolioError,
    rollup_recovery_portfolio,
)
from vertical_apps.industrial_claims.recovery_workflow import VindorumWorkflow
from vertical_apps.industrial_claims.service import IndustrialClaimsService


@dataclass(frozen=True)
class CurrentPortfolioCase:
    finding_id: str
    reconciliation_sequence: int
    reconciliation_hash: str


@dataclass(frozen=True)
class CurrentPortfolioSnapshot:
    rollup: PortfolioRecoveryRollup
    cases: tuple[CurrentPortfolioCase, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            **self.rollup.as_dict(),
            "current_case_reconciliations": [
                {
                    "finding_id": item.finding_id,
                    "sequence": item.reconciliation_sequence,
                    "reconciliation_hash": item.reconciliation_hash,
                }
                for item in self.cases
            ],
            "current_revision_only": True,
            "latest_reconciliation_only": True,
        }


class VindorumPortfolioWorkflow:
    """Build a VINDORUM portfolio only from current findings and their latest verified reconciliations."""

    def __init__(self, service: IndustrialClaimsService):
        self.service = service
        self.case_workflow = VindorumWorkflow(service)

    def build_current_portfolio(
        self,
        *,
        tenant_id: str,
        finding_ids: tuple[str, ...],
    ) -> CurrentPortfolioSnapshot:
        ids = tuple(str(item or "").strip() for item in finding_ids)
        if not ids or any(not item for item in ids):
            raise RecoveryPortfolioError("portfolio requires current finding ids")
        if len(set(ids)) != len(ids):
            raise RecoveryPortfolioError("duplicate finding_id would double count recovery")

        records = []
        cases = []
        for finding_id in ids:
            record = self.case_workflow.latest_reconciliation(
                tenant_id=tenant_id,
                finding_id=finding_id,
            )
            records.append(record)
            cases.append(
                CurrentPortfolioCase(
                    finding_id=finding_id,
                    reconciliation_sequence=record.sequence,
                    reconciliation_hash=record.reconciliation_hash,
                )
            )

        rollup = rollup_recovery_portfolio(tenant_id=tenant_id, records=tuple(records))
        return CurrentPortfolioSnapshot(rollup=rollup, cases=tuple(cases))
