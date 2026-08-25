from data_integrity import IntegrityFinding
from data_reconciliation import plan_reconciliation, report_plan_json


def _finding(invariant, owner="Owner"):
    return IntegrityFinding(
        invariant=invariant,
        severity="HIGH",
        tenant_ref="acct:opaque",
        stores=("a", "b"),
        expected="expected",
        observed="observed",
        owner=owner,
        repairable=True,
        unknown=False,
        exact_sha="deadbeef",
    )


def test_profile_ready_reconciliation_has_direction_but_no_automatic_repair():
    plan = plan_reconciliation(_finding("PROFILE_READY_EVENT_MISSING", owner="Evaluation"))

    assert plan.authoritative_side == "company_profiles canonical profile existence"
    assert plan.repair_direction.startswith("company_profiles -> Evaluation-owned")
    assert plan.automatic is False
    assert plan.blocker == "OWNER_IDEMPOTENT_EVENT_REPLAY_REQUIRED"
    assert plan.owner == "Evaluation"
    assert "repair twice" in plan.convergence_requirement


def test_unknown_repair_policy_fails_closed_without_timestamp_winner():
    plan = plan_reconciliation(_finding("PROFILE_READY_WITHOUT_PROFILE", owner="Company Profile + Evaluation"))

    assert plan.authoritative_side == "UNKNOWN"
    assert plan.repair_direction == "NONE_FAIL_CLOSED"
    assert plan.automatic is False
    assert plan.blocker == "UNKNOWN_AUTHORITY_OR_REPAIR_POLICY"
    assert "latest" not in plan.repair_direction.lower()


def test_reconciliation_plan_is_deterministic_machine_readable():
    finding = _finding("PROFILE_READY_EVENT_MISSING", owner="Evaluation")
    first = report_plan_json(plan_reconciliation(finding))
    second = report_plan_json(plan_reconciliation(finding))

    assert first == second
    assert '"automatic":false' in first
    assert "acct:opaque" not in first
