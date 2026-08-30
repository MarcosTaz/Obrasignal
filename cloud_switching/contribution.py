from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class ContributionPermission(str, Enum):
    WITHHELD = "withheld"
    INTERNAL_ANALYSIS_ONLY = "internal_analysis_only"
    DEIDENTIFIED_BENCHMARK = "deidentified_benchmark"


class AggregatePublicationPermission(str, Enum):
    WITHHELD = "withheld"
    AGGREGATE_ONLY = "aggregate_only"


@dataclass(frozen=True)
class OutcomeContributionConsent:
    tenant_id: str
    case_id: str
    contribution: ContributionPermission
    aggregate_publication: AggregatePublicationPermission
    granted_by: str
    granted_at: datetime
    policy_version: str

    @classmethod
    def create(
        cls,
        *,
        tenant_id: str,
        case_id: str,
        contribution: ContributionPermission,
        aggregate_publication: AggregatePublicationPermission,
        granted_by: str,
        policy_version: str,
        granted_at: datetime | None = None,
    ) -> "OutcomeContributionConsent":
        tenant = str(tenant_id or "").strip()
        case = str(case_id or "").strip()
        actor = str(granted_by or "").strip()
        version = str(policy_version or "").strip()
        when = granted_at or datetime.now(timezone.utc)
        if not tenant or not case or not actor or not version:
            raise ValueError("tenant_id, case_id, granted_by and policy_version are required")
        if when.tzinfo is None:
            raise ValueError("granted_at must be timezone-aware")
        if contribution is ContributionPermission.WITHHELD and aggregate_publication is not AggregatePublicationPermission.WITHHELD:
            raise ValueError("aggregate publication cannot be granted when contribution is withheld")
        return cls(
            tenant_id=tenant,
            case_id=case,
            contribution=contribution,
            aggregate_publication=aggregate_publication,
            granted_by=actor,
            granted_at=when.astimezone(timezone.utc),
            policy_version=version,
        )

    @property
    def benchmark_contribution_allowed(self) -> bool:
        return self.contribution is ContributionPermission.DEIDENTIFIED_BENCHMARK

    @property
    def aggregate_publication_allowed(self) -> bool:
        return (
            self.benchmark_contribution_allowed
            and self.aggregate_publication is AggregatePublicationPermission.AGGREGATE_ONLY
        )


def benchmark_eligible(*, outcome_verified: bool, consent: OutcomeContributionConsent | None) -> bool:
    """Benchmark inclusion needs both verified outcome truth and explicit consent."""
    return bool(
        outcome_verified
        and consent is not None
        and consent.benchmark_contribution_allowed
    )
