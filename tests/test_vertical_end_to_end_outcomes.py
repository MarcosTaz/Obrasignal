from datetime import date

from vertical_apps.aviation_recovery import AviationRecoveryService
from vertical_apps.contractcredit import ContractCreditService


def _complete(service, result, tenant_id, amount):
    finding_id = result["finding_id"]
    assert service.review(tenant_id=tenant_id, finding_id=finding_id, reviewer="reviewer", approved=True, reason="evidence supports assisted action") == "APPROVED"
    assert service.action(tenant_id=tenant_id, finding_id=finding_id) == "ACTIONED"
    outcome = service.resolve(tenant_id=tenant_id, finding_id=finding_id, outcome_id=f"{tenant_id}:outcome", recovered_amount=amount, currency="EUR", evidence_ref=f"{tenant_id}:settlement")
    return outcome


def test_aviation_end_to_end_to_recovered_outcome(tmp_path):
    service = AviationRecoveryService(tmp_path / "aviation.sqlite3")
    result = service.analyze(tenant_id="airline", actor_id="analyst", contract_ref="lease", event_ref="shop", eligible_cost="100000", reimbursed_amount="25000", notice_due=date(2026, 9, 30))
    outcome = _complete(service, result, "airline", "75000")
    assert outcome.state == "RECOVERED"
    assert service.ops.get_state(tenant_id="airline", finding_id=result["finding_id"]) == "RECOVERED"


def test_contractcredit_end_to_end_to_recovered_outcome(tmp_path):
    service = ContractCreditService(tmp_path / "credit.sqlite3")
    result = service.analyze(tenant_id="enterprise", actor_id="analyst", contract_ref="msa", incident_ref="sev1", monthly_fee="50000", credit_rate="0.10", notice_due=date(2026, 9, 15))
    outcome = _complete(service, result, "enterprise", "5000")
    assert outcome.state == "RECOVERED"
    assert service.ops.get_state(tenant_id="enterprise", finding_id=result["finding_id"]) == "RECOVERED"
