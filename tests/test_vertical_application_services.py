from datetime import date

from vertical_apps.aviation_recovery import AviationRecoveryService
from vertical_apps.contractcredit import ContractCreditService


def test_aviation_service_persists_assisted_case(tmp_path):
    service = AviationRecoveryService(tmp_path / "aviation.sqlite3")
    result = service.analyze(
        tenant_id="airline-1",
        actor_id="analyst-1",
        contract_ref="lease-1",
        event_ref="event-1",
        eligible_cost="100000",
        reimbursed_amount="25000",
        notice_due=date(2026, 9, 30),
    )
    assert result["potential_value"] == "75000"
    assert result["state"] == "READY_FOR_REVIEW"
    assert service.store.count("findings", "airline-1") == 1


def test_contractcredit_service_persists_assisted_case(tmp_path):
    service = ContractCreditService(tmp_path / "contractcredit.sqlite3")
    result = service.analyze(
        tenant_id="enterprise-1",
        actor_id="analyst-1",
        contract_ref="msa-1",
        incident_ref="incident-1",
        monthly_fee="50000",
        credit_rate="0.10",
        notice_due=date(2026, 9, 15),
    )
    assert result["potential_value"] == "5000.00"
    assert result["state"] == "READY_FOR_REVIEW"
    assert service.store.count("findings", "enterprise-1") == 1
