from __future__ import annotations

from datetime import datetime, timezone

import pytest

from vertical_apps.industrial_claims.intake_authorization import (
    IntakeAuthorization,
    IntakeAuthorizationError,
    recompute_intake_authorization_scope_sha256,
)
from vertical_apps.industrial_claims.outcome_authorization import (
    OutcomeAuthorizationError,
    OutcomeEvidenceAuthorization,
    recompute_outcome_authorization_scope_sha256,
)


NOW = datetime(2026, 9, 1, 21, 30, tzinfo=timezone.utc)


def _intake(max_bytes=1024) -> IntakeAuthorization:
    return IntakeAuthorization(
        authorization_id="auth-type-intake",
        tenant_id="tenant-a",
        case_ref="case-type",
        authorized_by_ref="controller@example.test",
        authorized_at="2026-09-01T20:00:00+00:00",
        expires_at="2026-09-02T20:00:00+00:00",
        minimum_immutable_retention_until="2027-09-02T20:00:00+00:00",
        transfer_channel_ref="secure-channel",
        evidence_roles=("commercial_basis", "event", "cost"),
        data_terms_state="SIGNED",
        immutable_retention_acknowledged=True,
        max_bytes_per_evidence=max_bytes,
    )


def _outcome(max_bytes=1024) -> OutcomeEvidenceAuthorization:
    return OutcomeEvidenceAuthorization(
        authorization_id="auth-type-outcome",
        tenant_id="tenant-a",
        finding_id="tenant-a:finding-type",
        authorized_by_ref="controller@example.test",
        authorized_at="2026-09-01T20:00:00+00:00",
        expires_at="2026-09-02T20:00:00+00:00",
        minimum_immutable_retention_until="2027-09-02T20:00:00+00:00",
        transfer_channel_ref="secure-outcome-channel",
        data_terms_state="SIGNED",
        immutable_retention_acknowledged=True,
        max_bytes=max_bytes,
    )


def test_live_authorizations_reject_boolean_byte_limits():
    with pytest.raises(IntakeAuthorizationError, match="byte limit"):
        _intake(True).validated(now=NOW)
    with pytest.raises(OutcomeAuthorizationError, match="byte limit"):
        _outcome(True).validated(now=NOW)


def test_persisted_scope_recomputation_rejects_boolean_byte_limits():
    intake = _intake().validated(now=NOW).metadata()
    intake["intake_max_bytes_per_evidence"] = True
    with pytest.raises(IntakeAuthorizationError, match="byte limit"):
        recompute_intake_authorization_scope_sha256(intake, tenant_id="tenant-a")

    outcome = _outcome().validated(now=NOW).metadata()
    outcome["outcome_max_bytes"] = True
    with pytest.raises(OutcomeAuthorizationError, match="byte limit"):
        recompute_outcome_authorization_scope_sha256(outcome, tenant_id="tenant-a")
