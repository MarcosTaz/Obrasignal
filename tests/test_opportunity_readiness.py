from datetime import datetime, timezone

import pytest

from opportunity_readiness import TenantBoundaryError, evaluate_readiness

NOW = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)


def opp(**overrides):
    data = {"id": 7, "external_id": "ABC", "source": "TED", "is_actionable": True,
            "lifecycle_status": "ACTIVE", "deadline": "2026-09-05T12:00:00+00:00", "value": 250000}
    data.update(overrides)
    return data


def req(status="MET", mandatory=True, name="certification", **extra):
    return {"status": status, "mandatory": mandatory, "name": name, **extra}


def assess(opportunity=None, requirements=None, economic=None, company=None):
    return evaluate_readiness("acct-a", opportunity or opp(), company or {"account_id": "acct-a"},
                              requirements=requirements,
                              economic_fit_result=economic or {"status": "FAVOURABLE", "reason": "ok", "rule_version": "economic-fit-v2"},
                              clock=NOW)


def test_open_opportunity_with_sufficient_known_data_is_ready():
    result = assess(requirements=[req()])
    assert result["overall_status"] == "READY"


def test_expired_deadline_blocks():
    result = assess(opp(deadline="2026-08-24T23:59:00+00:00"), [req()])
    assert result["overall_status"] == "NOT_READY"
    assert any(x["code"] == "submission_deadline_expired" for x in result["blocking_items"])


def test_deadline_due_exactly_at_clock_blocks():
    result = assess(opp(deadline=NOW.isoformat()), [req()])
    assert result["overall_status"] == "NOT_READY"
    assert any(x["code"] == "submission_deadline_expired" for x in result["blocking_items"])


def test_explicitly_closed_opportunity_blocks():
    result = assess(opp(is_actionable=False, lifecycle_status="CLOSED"), [req()])
    assert result["overall_status"] == "NOT_READY"


def test_sqlite_zero_actionable_blocks_even_without_lifecycle_label():
    result = assess(opp(is_actionable=0, lifecycle_status=None), [req()])
    assert result["overall_status"] == "NOT_READY"
    assert any(x["code"] == "opportunity_not_actionable" for x in result["blocking_items"])


def test_sqlite_one_actionable_is_explicitly_ready_even_without_lifecycle_label():
    result = assess(opp(is_actionable=1, lifecycle_status=None), [req()])
    assert result["overall_status"] == "READY"


def test_mandatory_known_blocker_blocks():
    assert assess(requirements=[req("NOT_MET")])["overall_status"] == "NOT_READY"


def test_false_ready_critical_requirement_unknown():
    result = assess(requirements=[req("UNKNOWN")])
    assert result["overall_status"] != "READY"
    assert result["overall_status"] == "UNKNOWN"


def test_unknown_requirement_priority_stays_critical():
    requirement = {"status": "UNKNOWN", "mandatory": None, "name": "unclassified obligation"}
    result = assess(requirements=[requirement])
    assert result["overall_status"] == "UNKNOWN"
    assert result["unknown_items"][0]["critical"] is True


def test_requirements_subsystem_missing_is_unknown_not_blocked():
    result = assess(requirements=None)
    assert result["overall_status"] == "UNKNOWN"
    assert not result["blocking_items"]


def test_missing_company_economic_data_is_unknown_not_blocked():
    result = evaluate_readiness("acct-a", opp(value=None), {"account_id": "acct-a"}, requirements=[req()], economic_fit_result={"status": "UNKNOWN", "reason": "missing"}, clock=NOW)
    assert result["overall_status"] == "CONDITIONALLY_READY"
    assert not result["blocking_items"]


def test_warning_without_blocker_is_conditionally_ready():
    result = assess(opp(deadline="2026-08-26T12:00:00+00:00"), [req()])
    assert result["overall_status"] == "CONDITIONALLY_READY"
    assert result["warning_items"]


def test_optional_requirement_not_met_is_warning_not_blocker():
    result = assess(requirements=[req("NOT_MET", mandatory=False)])
    assert result["overall_status"] == "CONDITIONALLY_READY"
    assert not result["blocking_items"]


def test_multiple_blockers_retained():
    result = assess(opp(deadline="2026-08-20T00:00:00+00:00", is_actionable=False, lifecycle_status="CANCELLED"), [req("NOT_MET")])
    assert len(result["blocking_items"]) >= 3


def test_deterministic_same_inputs_same_clock():
    a = assess(requirements=[req()])
    b = assess(requirements=[req()])
    assert a == b


def test_evidence_refs_retained():
    result = assess(requirements=[req(evidence_ref="evidence:req:1")], economic={"status": "FAVOURABLE", "reason": "ok", "rule_version": "economic-fit-v2"})
    assert "evidence:req:1" in result["evidence_refs"]
    assert "economic-fit-v2" in result["evidence_refs"]


def test_cross_tenant_company_state_rejected():
    with pytest.raises(TenantBoundaryError):
        evaluate_readiness("acct-a", opp(), {"account_id": "acct-b"}, requirements=[req()], clock=NOW)


def test_fixed_clock_behavior():
    before = assess(opp(deadline="2026-08-26T00:00:00+00:00"), [req()])
    assert before["dimensions"]["DEADLINE"]["status"] == "WARNING"
    after = evaluate_readiness("acct-a", opp(deadline="2026-08-26T00:00:00+00:00"), {"account_id": "acct-a"}, requirements=[req()], economic_fit_result={"status": "FAVOURABLE", "reason": "ok"}, clock=datetime(2026, 8, 27, tzinfo=timezone.utc))
    assert after["overall_status"] == "NOT_READY"


def test_invalid_deadline_is_unknown_not_false_blocker():
    result = assess(opp(deadline="not-a-date"), [req()])
    assert result["overall_status"] == "UNKNOWN"
    assert not result["blocking_items"]
