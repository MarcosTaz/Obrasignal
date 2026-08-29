from datetime import date

from factory_cloud.recovery_index import RecoveryIndex
from vertical_apps.aviation_recovery import AviationRecoveryService
from vertical_apps.contractcredit import ContractCreditService


def test_replay_marks_existing_recovery_without_duplicate_index_row(tmp_path):
    service = ContractCreditService(tmp_path / "credit.sqlite3")
    kwargs = dict(tenant_id="enterprise", actor_id="analyst", contract_ref="msa", incident_ref="inc", monthly_fee="1000", credit_rate="0.10", notice_due=date(2026, 9, 15))
    first = service.analyze(**kwargs)
    second = service.analyze(**kwargs)
    assert first["new_recovery_record"] == "true"
    assert second["new_recovery_record"] == "false"
    assert first["recovery_fingerprint"] == second["recovery_fingerprint"]
    assert service.index.count_fingerprints("enterprise") == 1


def test_same_source_refs_do_not_collide_across_tenants(tmp_path):
    database = tmp_path / "aviation.sqlite3"
    service = AviationRecoveryService(database)
    common = dict(actor_id="analyst", contract_ref="lease", event_ref="event", eligible_cost="100", reimbursed_amount="0", notice_due=date(2026, 9, 30))
    a = service.analyze(tenant_id="airline-a", **common)
    b = service.analyze(tenant_id="airline-b", **common)
    assert a["new_recovery_record"] == "true"
    assert b["new_recovery_record"] == "true"
    index = RecoveryIndex(database)
    assert index.count_fingerprints("airline-a") == 1
    assert index.count_fingerprints("airline-b") == 1
