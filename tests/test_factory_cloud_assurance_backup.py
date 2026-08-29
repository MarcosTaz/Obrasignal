from datetime import date

from factory_cloud.assurance_backup import create_backup, restore_backup
from factory_cloud.assurance_store import AssuranceStore
from vertical_apps.aviation_recovery.service import AviationRecoveryService
from vertical_apps.contractcredit.service import ContractCreditService


def _roundtrip(source, restored):
    backup = source.with_suffix(".backup.sqlite3")
    record = create_backup(source, backup)
    assert record.integrity == "ok"
    restore = restore_backup(backup, restored)
    assert restore.integrity == "ok"
    return AssuranceStore(restored)


def test_backup_contract_reuses_across_aviation_and_contractcredit(tmp_path):
    aviation_db = tmp_path / "aviation.sqlite3"
    aviation = AviationRecoveryService(aviation_db)
    aviation.analyze(
        tenant_id="airline",
        actor_id="analyst",
        contract_ref="lease-1",
        event_ref="shopvisit-1",
        eligible_cost="100000",
        reimbursed_amount="25000",
        notice_due=date(2026, 9, 30),
    )
    restored_aviation = _roundtrip(aviation_db, tmp_path / "aviation-restored.sqlite3")
    assert restored_aviation.count("findings", "airline") == 1
    assert restored_aviation.count("evidence", "airline") == 2

    credit_db = tmp_path / "credit.sqlite3"
    credit = ContractCreditService(credit_db)
    credit.analyze(
        tenant_id="enterprise",
        actor_id="analyst",
        contract_ref="msa-1",
        incident_ref="incident-1",
        monthly_fee="10000",
        credit_rate="0.10",
        notice_due=date(2026, 9, 30),
    )
    restored_credit = _roundtrip(credit_db, tmp_path / "credit-restored.sqlite3")
    assert restored_credit.count("findings", "enterprise") == 1
    assert restored_credit.count("evidence", "enterprise") == 2
