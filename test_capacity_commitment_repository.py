import sqlite3
from decimal import Decimal

import pytest

from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.state import AssistedCaseState
from factories.capacity_commitment.synthetic_cases import case


def make_state(tenant_id: str, case_id: str) -> AssistedCaseState:
    return AssistedCaseState(
        tenant_id=tenant_id,
        company_id=f"company-{tenant_id}",
        customer_id="oem-1",
        program_id="program-1",
        recovery_case=case(case_id),
        evidence_refs=("contract:1",),
        contract_id="lta-2026-01",
        forecast_units=Decimal("110000"),
    )


def test_repository_save_return_persists_across_reopen(tmp_path):
    db_path = tmp_path / "capacity.db"
    repo = CapacityRepository(str(db_path))
    state = make_state("tenant-a", "case-1")
    repo.save(state)

    reopened = CapacityRepository(str(db_path))
    restored = reopened.load(tenant_id="tenant-a", case_id="case-1")
    assert restored == state


def test_repository_cross_tenant_lookup_returns_nothing(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    repo.save(make_state("tenant-a", "case-1"))

    with pytest.raises(KeyError, match="not found"):
        repo.load(tenant_id="tenant-b", case_id="case-1")
    assert repo.list_case_ids(tenant_id="tenant-b") == []


def test_repository_same_case_id_isolated_per_tenant(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    repo.save(make_state("tenant-a", "same-case"))
    repo.save(make_state("tenant-b", "same-case"))

    assert repo.load(tenant_id="tenant-a", case_id="same-case").tenant_id == "tenant-a"
    assert repo.load(tenant_id="tenant-b", case_id="same-case").tenant_id == "tenant-b"


def test_repository_backup_restore_roundtrip(tmp_path):
    live_path = tmp_path / "live.db"
    backup_path = tmp_path / "backup.db"
    repo = CapacityRepository(str(live_path))
    original = make_state("tenant-a", "case-original")
    repo.save(original)
    repo.backup_to(str(backup_path))

    repo.save(make_state("tenant-a", "case-after-backup"))
    assert set(repo.list_case_ids(tenant_id="tenant-a")) == {"case-original", "case-after-backup"}

    repo.restore_from(str(backup_path))
    assert repo.load(tenant_id="tenant-a", case_id="case-original") == original
    with pytest.raises(KeyError):
        repo.load(tenant_id="tenant-a", case_id="case-after-backup")


def test_repository_rejects_corrupted_backup_before_live_mutation(tmp_path):
    live_path = tmp_path / "live.db"
    backup_path = tmp_path / "bad-backup.db"
    repo = CapacityRepository(str(live_path))
    original = make_state("tenant-a", "case-original")
    repo.save(original)

    bad = CapacityRepository(str(backup_path))
    bad.save(make_state("tenant-a", "bad-case"))
    with sqlite3.connect(backup_path) as conn:
        conn.execute(
            "UPDATE capacity_commitment_cases SET snapshot='{}' WHERE case_id='bad-case'"
        )

    with pytest.raises(ValueError):
        repo.restore_from(str(backup_path))

    assert repo.load(tenant_id="tenant-a", case_id="case-original") == original


def test_repository_requires_durable_path():
    with pytest.raises(ValueError):
        CapacityRepository(":memory:")
