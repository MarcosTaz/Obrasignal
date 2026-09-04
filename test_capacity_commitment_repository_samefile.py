import os

import pytest

from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.state import AssistedCaseState
from factories.capacity_commitment.synthetic_cases import case


def _state(case_id: str) -> AssistedCaseState:
    return AssistedCaseState(
        tenant_id="tenant-a",
        company_id="supplier-a",
        customer_id="oem-a",
        program_id="program-a",
        contract_id="lta-1",
        recovery_case=case(case_id),
        evidence_refs=("contract:1",),
        deadline="2099-12-31",
    )


def test_backup_rejects_different_path_to_same_physical_database(tmp_path):
    live = tmp_path / "live.db"
    alias = tmp_path / "alias.db"
    repo = CapacityRepository(str(live))
    repo.save(_state("samefile-backup"))
    os.link(live, alias)

    with pytest.raises(ValueError, match="differ from source"):
        repo.backup_to(str(alias))


def test_restore_rejects_different_path_to_same_physical_database(tmp_path):
    live = tmp_path / "live.db"
    alias = tmp_path / "alias.db"
    repo = CapacityRepository(str(live))
    original = _state("samefile-restore")
    repo.save(original)
    os.link(live, alias)

    with pytest.raises(ValueError, match="differ from destination"):
        repo.restore_from(str(alias))

    assert repo.load(tenant_id="tenant-a", case_id="samefile-restore") == original
