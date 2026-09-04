import pytest

from vertical_apps.industrial_claims.leakage_reconciliation import (
    LeakageReconciliationError,
    reconcile_recovery_ledger,
)
from vertical_apps.industrial_claims.recovery_reconciliation_store import (
    RecoveryReconciliationStore,
    RecoveryReconciliationStoreError,
)


def _snapshot(*, claimed="40", approved="30", settled="20", supported="80"):
    return reconcile_recovery_ledger(
        documented_cost="100",
        mitigation="10",
        evidence_supported=supported,
        claimed=claimed,
        approved=approved,
        settled=settled,
        currency="EUR",
    )


def test_append_only_reconciliation_history_and_latest_are_tenant_scoped(tmp_path):
    store = RecoveryReconciliationStore(tmp_path / "reconciliation.sqlite3")
    first = store.append(
        tenant_id="alpha",
        finding_id="finding-1",
        snapshot=_snapshot(),
        actor_id="reviewer-1",
        evidence_ref="review-pack-v1",
    )
    second = store.append(
        tenant_id="alpha",
        finding_id="finding-1",
        snapshot=_snapshot(claimed="60", approved="45", settled="35"),
        actor_id="reviewer-2",
        evidence_ref="claim-ledger-v2",
    )
    store.append(
        tenant_id="beta",
        finding_id="finding-1",
        snapshot=_snapshot(claimed="50", approved="40", settled="30"),
        actor_id="reviewer-beta",
        evidence_ref="beta-pack",
    )

    assert first.sequence == 1
    assert second.sequence == 2
    assert store.latest(tenant_id="alpha", finding_id="finding-1").reconciliation_hash == second.reconciliation_hash
    assert [item.sequence for item in store.history(tenant_id="alpha", finding_id="finding-1")] == [1, 2]
    assert [item.sequence for item in store.history(tenant_id="beta", finding_id="finding-1")] == [1]


def test_exact_replay_is_idempotent_but_metadata_rebinding_fails(tmp_path):
    store = RecoveryReconciliationStore(tmp_path / "replay.sqlite3")
    snapshot = _snapshot()
    first = store.append(
        tenant_id="alpha",
        finding_id="finding-1",
        snapshot=snapshot,
        actor_id="reviewer-1",
        evidence_ref="pack-1",
    )
    replay = store.append(
        tenant_id="alpha",
        finding_id="finding-1",
        snapshot=snapshot,
        actor_id="reviewer-1",
        evidence_ref="pack-1",
    )

    assert replay.sequence == first.sequence
    assert len(store.history(tenant_id="alpha", finding_id="finding-1")) == 1

    with pytest.raises(RecoveryReconciliationStoreError, match="replay metadata"):
        store.append(
            tenant_id="alpha",
            finding_id="finding-1",
            snapshot=snapshot,
            actor_id="different-actor",
            evidence_ref="pack-1",
        )


def test_economic_decrease_requires_explicit_reversal_reason(tmp_path):
    store = RecoveryReconciliationStore(tmp_path / "reversal.sqlite3")
    store.append(
        tenant_id="alpha",
        finding_id="finding-1",
        snapshot=_snapshot(claimed="70", approved="60", settled="50"),
        actor_id="reviewer-1",
        evidence_ref="settlement-v1",
    )
    corrected = _snapshot(claimed="65", approved="55", settled="45")

    with pytest.raises(RecoveryReconciliationStoreError, match="economic decrease requires reversal_reason"):
        store.append(
            tenant_id="alpha",
            finding_id="finding-1",
            snapshot=corrected,
            actor_id="reviewer-2",
            evidence_ref="credit-note-v2",
        )

    persisted = store.append(
        tenant_id="alpha",
        finding_id="finding-1",
        snapshot=corrected,
        actor_id="reviewer-2",
        evidence_ref="credit-note-v2",
        reversal_reason="Counterparty correction reduced the approved and settled amounts; evidence retained in credit-note-v2.",
    )
    assert persisted.sequence == 2
    assert persisted.reversal_reason is not None
    assert persisted.snapshot["settled"] == "45"


def test_unsupported_or_unapproved_value_cannot_bypass_snapshot_invariants(tmp_path):
    store = RecoveryReconciliationStore(tmp_path / "invalid.sqlite3")
    with pytest.raises(LeakageReconciliationError, match="claimed amount cannot exceed evidence-supported amount"):
        reconcile_recovery_ledger(
            documented_cost="100",
            mitigation="0",
            evidence_supported="60",
            claimed="70",
            approved="0",
            settled="0",
            currency="EUR",
        )
    assert store.history(tenant_id="alpha", finding_id="finding-1") == ()
