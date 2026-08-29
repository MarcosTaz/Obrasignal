from datetime import date

import pytest

from factory_cloud.assurance_backup import AssuranceBackupError, create_backup, restore_backup
from factory_cloud.assurance_store import AssuranceStore
from vertical_apps.contractcredit import ContractCreditService


def _seed(path):
    service = ContractCreditService(path)
    result = service.analyze(
        tenant_id="synthetic-enterprise",
        actor_id="analyst",
        contract_ref="msa-synthetic",
        incident_ref="incident-synthetic",
        monthly_fee="50000",
        credit_rate="0.10",
        notice_due=date(2026, 9, 15),
    )
    return service, result


def test_verified_backup_restore_preserves_assurance_case(tmp_path):
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backups" / "case.sqlite3"
    restored = tmp_path / "restored.sqlite3"
    service, result = _seed(source)
    before = {
        table: service.store.count(table, "synthetic-enterprise")
        for table in ("evidence", "calculations", "deadlines", "findings", "audit_events", "notification_outbox")
    }

    receipt = create_backup(source, backup)
    assert receipt.integrity == "ok"
    assert len(receipt.sha256) == 64
    assert receipt.schema_version == 1

    restore_backup(backup, restored, expected_sha256=receipt.sha256)
    restored_store = AssuranceStore(restored)
    after = {table: restored_store.count(table, "synthetic-enterprise") for table in before}
    assert after == before
    assert result["finding_id"]


def test_restore_rejects_tampered_backup_digest(tmp_path):
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    _seed(source)
    receipt = create_backup(source, backup)
    with backup.open("ab") as handle:
        handle.write(b"tamper")
    with pytest.raises(AssuranceBackupError, match="digest mismatch"):
        restore_backup(backup, tmp_path / "restored.sqlite3", expected_sha256=receipt.sha256)


def test_backup_and_restore_refuse_destructive_overwrite(tmp_path):
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    restored = tmp_path / "restored.sqlite3"
    _seed(source)
    receipt = create_backup(source, backup)
    with pytest.raises(AssuranceBackupError, match="already exists"):
        create_backup(source, backup)
    restored.write_bytes(b"existing")
    with pytest.raises(AssuranceBackupError, match="already exists"):
        restore_backup(backup, restored, expected_sha256=receipt.sha256)
