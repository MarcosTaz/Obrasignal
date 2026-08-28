import sqlite3
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

import pytest

from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.state import AssistedCaseState
from factories.capacity_commitment.synthetic_cases import case


def make_state(tenant_id: str, case_id: str, *, actual_units=Decimal("80000")) -> AssistedCaseState:
    return AssistedCaseState(
        tenant_id=tenant_id,
        company_id=f"company-{tenant_id}",
        customer_id="oem-1",
        program_id="program-1",
        recovery_case=case(case_id, actual_units=actual_units),
        evidence_refs=("contract:1",),
        contract_id="lta-2026-01",
        forecast_units=Decimal("110000"),
        deadline="2026-09-30",
    )


def test_repository_save_return_persists_across_reopen(tmp_path):
    db_path = tmp_path / "capacity.db"
    repo = CapacityRepository(str(db_path))
    state = make_state("tenant-a", "case-1")
    assert repo.save(state) is True

    reopened = CapacityRepository(str(db_path))
    restored = reopened.load(tenant_id="tenant-a", case_id="case-1")
    assert restored == state


def test_repository_exact_retry_is_idempotent_and_preserves_single_state(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    state = make_state("tenant-a", "retry-case")
    assert repo.save(state) is True
    assert repo.save(state) is False
    assert repo.list_case_ids(tenant_id="tenant-a") == ["retry-case"]
    assert repo.load(tenant_id="tenant-a", case_id="retry-case") == state


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


def test_repository_duplicate_same_tenant_fails_without_overwrite(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    original = make_state("tenant-a", "same-case", actual_units=Decimal("80000"))
    changed = make_state("tenant-a", "same-case", actual_units=Decimal("0"))
    repo.save(original)

    with pytest.raises(FileExistsError, match="different source state"):
        repo.save(changed)

    assert repo.load(tenant_id="tenant-a", case_id="same-case") == original


def test_repository_concurrent_duplicate_create_has_one_winner_and_no_overwrite(tmp_path):
    db_path = str(tmp_path / "capacity.db")
    CapacityRepository(db_path)  # create schema before racing writers
    barrier = Barrier(2)
    candidates = [
        make_state("tenant-a", "concurrent-case", actual_units=Decimal("80000")),
        make_state("tenant-a", "concurrent-case", actual_units=Decimal("0")),
    ]

    def attempt(state):
        repo = CapacityRepository(db_path)
        barrier.wait()
        try:
            created = repo.save(state)
            return "saved" if created else "replayed", state.recovery_case.actual_units
        except FileExistsError:
            return "conflict", state.recovery_case.actual_units

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, candidates))

    assert sorted(status for status, _ in outcomes) == ["conflict", "saved"]
    restored = CapacityRepository(db_path).load(tenant_id="tenant-a", case_id="concurrent-case")
    winning_actual = next(actual for status, actual in outcomes if status == "saved")
    assert restored.recovery_case.actual_units == winning_actual


def test_repository_engine_version_drift_requires_explicit_reassessment(tmp_path):
    db_path = tmp_path / "capacity.db"
    repo = CapacityRepository(str(db_path))
    repo.save(make_state("tenant-a", "versioned-case"))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE capacity_commitment_cases SET engine_version='legacy-engine' WHERE case_id='versioned-case'"
        )

    with pytest.raises(RuntimeError, match="explicit reassessment"):
        repo.load(tenant_id="tenant-a", case_id="versioned-case")


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


def test_repository_rejects_version_drift_backup_before_live_mutation(tmp_path):
    live_path = tmp_path / "live.db"
    backup_path = tmp_path / "old-engine-backup.db"
    repo = CapacityRepository(str(live_path))
    original = make_state("tenant-a", "case-original")
    repo.save(original)

    old = CapacityRepository(str(backup_path))
    old.save(make_state("tenant-a", "old-case"))
    with sqlite3.connect(backup_path) as conn:
        conn.execute("UPDATE capacity_commitment_cases SET engine_version='legacy-engine'")

    with pytest.raises(ValueError, match="engine reassessment"):
        repo.restore_from(str(backup_path))

    assert repo.load(tenant_id="tenant-a", case_id="case-original") == original


def test_repository_requires_durable_path():
    with pytest.raises(ValueError):
        CapacityRepository(":memory:")
