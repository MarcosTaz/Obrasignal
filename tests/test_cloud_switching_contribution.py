from datetime import datetime, timezone

import pytest

from cloud_switching.contribution import (
    AggregatePublicationPermission,
    ContributionPermission,
    OutcomeContributionConsent,
    benchmark_eligible,
)


def test_verified_outcome_without_explicit_benchmark_consent_is_not_eligible():
    assert benchmark_eligible(outcome_verified=True, consent=None) is False


def test_deidentified_contribution_and_publication_are_separate_permissions():
    consent = OutcomeContributionConsent.create(
        tenant_id="customer-a",
        case_id="case-1",
        contribution=ContributionPermission.DEIDENTIFIED_BENCHMARK,
        aggregate_publication=AggregatePublicationPermission.WITHHELD,
        granted_by="customer-reviewer",
        policy_version="benchmark-v1",
        granted_at=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
    )
    assert consent.benchmark_contribution_allowed is True
    assert consent.aggregate_publication_allowed is False
    assert benchmark_eligible(outcome_verified=True, consent=consent) is True
    assert benchmark_eligible(outcome_verified=False, consent=consent) is False


def test_withheld_contribution_cannot_grant_aggregate_publication():
    with pytest.raises(ValueError):
        OutcomeContributionConsent.create(
            tenant_id="customer-a",
            case_id="case-1",
            contribution=ContributionPermission.WITHHELD,
            aggregate_publication=AggregatePublicationPermission.AGGREGATE_ONLY,
            granted_by="customer-reviewer",
            policy_version="benchmark-v1",
        )


def test_consent_requires_timezone_aware_audit_time():
    with pytest.raises(ValueError):
        OutcomeContributionConsent.create(
            tenant_id="customer-a",
            case_id="case-1",
            contribution=ContributionPermission.INTERNAL_ANALYSIS_ONLY,
            aggregate_publication=AggregatePublicationPermission.WITHHELD,
            granted_by="customer-reviewer",
            policy_version="benchmark-v1",
            granted_at=datetime(2026, 8, 29, 12, 0),
        )
