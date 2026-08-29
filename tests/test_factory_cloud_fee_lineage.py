from datetime import date

import pytest

from factory_cloud.assurance_ops import AssuranceOperationError
from vertical_apps.aviation_recovery import AviationRecoveryService
from vertical_apps.contractcredit import ContractCreditService


def _recover(service, tenant, analyze_kwargs, recovered):
    result = service.analyze(tenant_id=tenant, actor_id="analyst", **analyze_kwargs)
    finding = result["finding_id"]
    service.review(tenant_id=tenant, finding_id=finding, reviewer="reviewer", approved=True, reason="supported")
    service.action(tenant_id=tenant, finding_id=finding)
    outcome = service.resolve(tenant_id=tenant, finding_id=finding, outcome_id=f"{tenant}:outcome", recovered_amount=recovered, currency="EUR", evidence_ref="settlement")
    return outcome


def test_fee_lineage_works_for_two_verticals(tmp_path):
    aviation = AviationRecoveryService(tmp_path / "aviation.sqlite3")
    a_outcome = _recover(aviation, "airline", dict(contract_ref="lease", event_ref="event", eligible_cost="100", reimbursed_amount="0", notice_due=date(2026, 9, 30)), "100")
    a_fee = aviation.ops.record_fee(tenant_id="airline", outcome_id=a_outcome.outcome_id, fee_id="airline:fee", fee_rate="0.20")
    assert a_fee.fee_amount == "20.00"

    credit = ContractCreditService(tmp_path / "credit.sqlite3")
    c_outcome = _recover(credit, "enterprise", dict(contract_ref="msa", incident_ref="inc", monthly_fee="1000", credit_rate="0.10", notice_due=date(2026, 9, 15)), "100")
    c_fee = credit.ops.record_fee(tenant_id="enterprise", outcome_id=c_outcome.outcome_id, fee_id="enterprise:fee", fee_rate="0.15")
    assert c_fee.fee_amount == "15.00"
    assert len(credit.ops.fees(tenant_id="enterprise")) == 1


def test_fee_lineage_rejects_other_tenant_and_zero_recovery(tmp_path):
    service = ContractCreditService(tmp_path / "credit.sqlite3")
    result = service.analyze(tenant_id="enterprise", actor_id="analyst", contract_ref="msa", incident_ref="inc", monthly_fee="1000", credit_rate="0.10", notice_due=date(2026, 9, 15))
    finding = result["finding_id"]
    service.review(tenant_id="enterprise", finding_id=finding, reviewer="r", approved=True, reason="supported")
    service.action(tenant_id="enterprise", finding_id=finding)
    outcome = service.resolve(tenant_id="enterprise", finding_id=finding, outcome_id="zero", recovered_amount="0", currency="EUR", evidence_ref="closure")
    with pytest.raises(AssuranceOperationError, match="recovered outcome"):
        service.ops.record_fee(tenant_id="enterprise", outcome_id=outcome.outcome_id, fee_id="fee", fee_rate="0.20")
    with pytest.raises(AssuranceOperationError, match="not found"):
        service.ops.record_fee(tenant_id="other", outcome_id=outcome.outcome_id, fee_id="other-fee", fee_rate="0.20")
