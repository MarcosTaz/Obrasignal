import sqlite3

import pytest

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.case_store import IndustrialCaseMetadata, IndustrialClaimsCaseStore
from vertical_apps.industrial_claims.revision_store import IndustrialCaseRevision, IndustrialClaimsRevisionStore


def _initial(finding_id="alpha:finding-1", tenant_id="alpha", fingerprint="fp-1"):
    return IndustrialCaseRevision(
        finding_id=finding_id,
        tenant_id=tenant_id,
        recovery_fingerprint=fingerprint,
        revision=1,
        supersedes_finding_id=None,
        is_current=True,
    )


def _legacy_case(finding_id="alpha:finding-1", tenant_id="alpha", fingerprint="fp-1"):
    return IndustrialCaseMetadata(
        finding_id=finding_id,
        tenant_id=tenant_id,
        claim_family="TOOLING",
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="event-1",
        entitlement_id=f"{tenant_id}:basis-1",
        deadline_id=f"{tenant_id}:deadline-1",
        recovery_fingerprint=fingerprint,
        notice_deadline_state="DECLARED_NONE_FOR_REVIEW",
        missing_evidence=(),
    )


def test_revision_store_registers_idempotent_initial_and_one_current_revision(tmp_path):
    store = IndustrialClaimsRevisionStore(tmp_path / "revisions.sqlite3")
    first = store.register_initial(_initial())
    replay = store.register_initial(_initial())
    assert replay == first
    assert store.count("alpha") == 1
    assert store.require_current(tenant_id="alpha", finding_id="alpha:finding-1") == first
    assert store.current_for_fingerprint(tenant_id="alpha", recovery_fingerprint="fp-1") == first

    with pytest.raises(AssuranceStoreError, match="already has a current revision"):
        store.register_initial(_initial(finding_id="alpha:other-finding"))
    assert store.count("alpha") == 1


def test_revision_store_backfills_one_legacy_case_as_revision_one(tmp_path):
    database = tmp_path / "revision-backfill.sqlite3"
    cases = IndustrialClaimsCaseStore(database)
    cases.put(_legacy_case())

    revisions = IndustrialClaimsRevisionStore(database)
    record = revisions.require_current(tenant_id="alpha", finding_id="alpha:finding-1")
    assert record.revision == 1
    assert record.recovery_fingerprint == "fp-1"
    assert record.supersedes_finding_id is None
    assert revisions.count("alpha") == 1


def test_revision_store_refuses_ambiguous_legacy_backfill(tmp_path):
    database = tmp_path / "revision-backfill-ambiguous.sqlite3"
    cases = IndustrialClaimsCaseStore(database)
    cases.put(_legacy_case())
    cases.put(_legacy_case(finding_id="alpha:finding-2"))

    with pytest.raises(AssuranceStoreError, match="ambiguous pre-revision industrial case lineage"):
        IndustrialClaimsRevisionStore(database)


def test_revision_store_supersedes_current_and_blocks_historical_current_use(tmp_path):
    store = IndustrialClaimsRevisionStore(tmp_path / "supersede.sqlite3")
    store.register_initial(_initial())
    second = store.supersede(
        tenant_id="alpha",
        recovery_fingerprint="fp-1",
        current_finding_id="alpha:finding-1",
        new_finding_id="alpha:finding-2",
    )
    assert second.revision == 2
    assert second.supersedes_finding_id == "alpha:finding-1"
    assert second.is_current is True
    assert store.get(tenant_id="alpha", finding_id="alpha:finding-1").is_current is False
    assert store.require_current(tenant_id="alpha", finding_id="alpha:finding-2") == second
    with pytest.raises(AssuranceStoreError, match="superseded"):
        store.require_current(tenant_id="alpha", finding_id="alpha:finding-1")


def test_revision_store_rejects_wrong_target_cross_tenant_and_control_characters(tmp_path):
    store = IndustrialClaimsRevisionStore(tmp_path / "revision-guards.sqlite3")
    store.register_initial(_initial())
    store.register_initial(_initial(finding_id="beta:finding-1", tenant_id="beta", fingerprint="fp-1"))

    with pytest.raises(AssuranceStoreError, match="not the current revision"):
        store.supersede(
            tenant_id="alpha", recovery_fingerprint="fp-1", current_finding_id="alpha:not-current", new_finding_id="alpha:finding-2"
        )
    with pytest.raises(AssuranceStoreError, match="tenant-scoped industrial revision not found"):
        store.get(tenant_id="beta", finding_id="alpha:finding-1")
    with pytest.raises(AssuranceStoreError, match="finding_id is invalid"):
        store.get(tenant_id="alpha", finding_id="alpha:finding-1\n")
    assert store.count("alpha") == 1
    assert store.count("beta") == 1


def test_supersession_inside_external_transaction_rolls_back_atomically(tmp_path):
    database = tmp_path / "revision-rollback.sqlite3"
    store = IndustrialClaimsRevisionStore(database)
    store.register_initial(_initial())

    with sqlite3.connect(database) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN IMMEDIATE")
        created = store.supersede(
            tenant_id="alpha",
            recovery_fingerprint="fp-1",
            current_finding_id="alpha:finding-1",
            new_finding_id="alpha:finding-2",
            connection=conn,
        )
        assert created.revision == 2
        conn.rollback()

    assert store.count("alpha") == 1
    assert store.require_current(tenant_id="alpha", finding_id="alpha:finding-1").revision == 1
    with pytest.raises(AssuranceStoreError, match="not found"):
        store.get(tenant_id="alpha", finding_id="alpha:finding-2")
