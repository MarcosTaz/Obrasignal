from datetime import date

import pytest

from factory_cloud.assurance_ops import AssuranceOperationError, AssuranceOperations
from vertical_apps.contractcredit import ContractCreditService


def _finding(tmp_path):
    service = ContractCreditService(tmp_path / "case.sqlite3")
    result = service.analyze(
        tenant_id="tenant-a",
        actor_id="analyst",
        contract_ref="msa",
        incident_ref="incident",
        monthly_fee="1000",
        credit_rate="0.10",
        notice_due=date(2026, 9, 30),
    )
    return service, result["finding_id"]


def test_review_action_recovery_is_durable_and_tenant_scoped(tmp_path):
    service, finding_id = _finding(tmp_path)
    ops = AssuranceOperations(service.store)
    assert ops.review(tenant_id="tenant-a", finding_id=finding_id, reviewer="reviewer", approved=True, reason="contract and incident evidence support review") == "APPROVED"
    assert ops.action(tenant_id="tenant-a", finding_id=finding_id) == "ACTIONED"
    outcome = ops.resolve(
        tenant_id="tenant-a",
        finding_id=finding_id,
        outcome_id="outcome-1",
        recovered_amount="100.00",
        currency="EUR",
        evidence_ref="credit-note-1",
    )
    assert outcome.state == "RECOVERED"
    assert ops.get_state(tenant_id="tenant-a", finding_id=finding_id) == "RECOVERED"
    assert len(ops.outcomes(tenant_id="tenant-a")) == 1
    assert len(ops.outcomes(tenant_id="other")) == 0


def test_review_reject_and_invalid_transitions_fail_closed(tmp_path):
    service, finding_id = _finding(tmp_path)
    ops = AssuranceOperations(service.store)
    with pytest.raises(AssuranceOperationError, match="not found"):
        ops.review(tenant_id="other", finding_id=finding_id, reviewer="r", approved=True, reason="x")
    assert ops.review(tenant_id="tenant-a", finding_id=finding_id, reviewer="r", approved=False, reason="insufficient basis") == "REJECTED"
    with pytest.raises(AssuranceOperationError, match="approved"):
        ops.action(tenant_id="tenant-a", finding_id=finding_id)


def test_zero_recovery_closes_without_fabricated_value(tmp_path):
    service, finding_id = _finding(tmp_path)
    ops = AssuranceOperations(service.store)
    ops.review(tenant_id="tenant-a", finding_id=finding_id, reviewer="r", approved=True, reason="supported")
    ops.action(tenant_id="tenant-a", finding_id=finding_id)
    outcome = ops.resolve(
        tenant_id="tenant-a",
        finding_id=finding_id,
        outcome_id="outcome-zero",
        recovered_amount="0",
        currency="EUR",
        evidence_ref="closure-1",
    )
    assert outcome.state == "CLOSED_NO_RECOVERY"
