from engineering_ops_gate_attribution import (
    ATTRIBUTION_STATES,
    TRIGGER_AWARENESS_STATES,
    classify_gate_attribution,
    classify_trigger_awareness,
    complete_required_gates,
    evaluate_owner_gate_state,
    extract_pull_request_paths,
    workflow_has_manual_dispatch,
)


def test_attribution_contract_is_bounded():
    assert ATTRIBUTION_STATES == (
        "REQUIRED",
        "INCIDENTALLY_TRIGGERED",
        "NOT_APPLICABLE",
        "REQUIRED_NOT_RUN",
        "NEEDS_RECHECK",
    )
    assert TRIGGER_AWARENESS_STATES == (
        "AUTO_TRIGGER_EXPECTED",
        "AUTO_TRIGGER_FILTERED_LEGITIMATELY",
        "MANUAL_DISPATCH_AVAILABLE",
        "WORKFLOW_MISSING",
        "REQUIRED_NOT_RUN",
        "ATTRIBUTION_UNKNOWN",
    )


def test_failed_incidental_gate_does_not_make_owner_red():
    attribution = classify_gate_attribution(
        workflow="Golden GP03 Economic Operational Truth",
        workflow_path=".github/workflows/golden-gp03.yml",
        changed_paths={"engineering_ops.py", "tests/test_engineering_ops.py"},
        candidate_workflow_paths={".github/workflows/engineering-ops-drift.yml"},
        run_trigger_pr=413,
        candidate_pr=407,
    )
    assert attribution.state == "INCIDENTALLY_TRIGGERED"
    state, _ = evaluate_owner_gate_state(
        [
            {"workflow": attribution.workflow, "attribution": attribution.state, "gate_state": "FAIL"},
            {"workflow": "ObraSignal Quality", "attribution": "REQUIRED", "gate_state": "PASS"},
            {"workflow": "Engineering Ops Drift", "attribution": "REQUIRED", "gate_state": "PASS"},
        ]
    )
    assert state == "OWNER_CURRENT_GREEN"


def test_required_failed_gate_is_red():
    state, reason = evaluate_owner_gate_state(
        [{"workflow": "Billing Security", "attribution": "REQUIRED", "gate_state": "FAIL"}]
    )
    assert state == "RED"
    assert "required gate failed" in reason


def test_required_not_run_is_never_green():
    missing = complete_required_gates(required_workflows={"JWT Verifier Live Gate"}, observed_gate_states={})
    assert missing[0].state == "REQUIRED_NOT_RUN"
    state, _ = evaluate_owner_gate_state(
        [{"workflow": missing[0].workflow, "attribution": missing[0].state, "gate_state": "NOT_RUN"}]
    )
    assert state == "NEEDS_RECHECK"


def test_unknown_attribution_is_never_green():
    attribution = classify_gate_attribution(
        workflow="Unknown Gate", workflow_path=None, changed_paths={"engineering_ops.py"}, candidate_pr=407
    )
    assert attribution.state == "NEEDS_RECHECK"
    state, _ = evaluate_owner_gate_state(
        [{"workflow": attribution.workflow, "attribution": attribution.state, "gate_state": "PASS"}]
    )
    assert state == "NEEDS_RECHECK"


def test_path_filtered_present_workflow_can_be_not_applicable():
    attribution = classify_gate_attribution(
        workflow="Auth Gate",
        workflow_path=".github/workflows/auth.yml",
        changed_paths={"docs/README.md"},
        candidate_workflow_paths={".github/workflows/auth.yml"},
        path_filters=("auth/**", "auth_context_jwt.py"),
        candidate_pr=99,
        run_trigger_pr=99,
    )
    assert attribution.state == "NOT_APPLICABLE"
    awareness = classify_trigger_awareness(
        attribution=attribution.state,
        gate_state="NOT_RUN",
        workflow_present=True,
        path_filters=("auth/**", "auth_context_jwt.py"),
        changed_paths={"docs/README.md"},
        manual_dispatch_available=True,
    )
    assert awareness == "AUTO_TRIGGER_FILTERED_LEGITIMATELY"


def test_required_not_run_is_not_excused_by_manual_dispatch():
    awareness = classify_trigger_awareness(
        attribution="REQUIRED_NOT_RUN",
        gate_state="NOT_RUN",
        workflow_present=True,
        path_filters=("engineering_ops.py",),
        changed_paths={"engineering_ops.py"},
        manual_dispatch_available=True,
    )
    assert awareness == "REQUIRED_NOT_RUN"


def test_missing_workflow_is_distinct_from_required_not_run():
    awareness = classify_trigger_awareness(
        attribution="REQUIRED",
        gate_state="NOT_RUN",
        workflow_present=False,
        path_filters=None,
        changed_paths={"engineering_ops.py"},
        manual_dispatch_available=False,
    )
    assert awareness == "WORKFLOW_MISSING"


def test_manual_dispatch_availability_is_detected():
    text = "name: Ops\non:\n  pull_request:\n  workflow_dispatch:\n"
    assert workflow_has_manual_dispatch(text)
    awareness = classify_trigger_awareness(
        attribution="REQUIRED",
        gate_state="NOT_RUN",
        workflow_present=True,
        path_filters=None,
        changed_paths={"engineering_ops.py"},
        manual_dispatch_available=True,
    )
    assert awareness == "MANUAL_DISPATCH_AVAILABLE"


def test_explicit_requirement_overrides_path_or_incidental_context():
    attribution = classify_gate_attribution(
        workflow="Golden GP03 Economic Operational Truth",
        workflow_path=".github/workflows/golden-gp03.yml",
        changed_paths={"engineering_ops.py"},
        explicit_required_workflows={"Golden GP03 Economic Operational Truth"},
        candidate_workflow_paths=set(),
        run_trigger_pr=413,
        candidate_pr=407,
    )
    assert attribution.state == "REQUIRED"


def test_unfiltered_present_workflow_is_required():
    attribution = classify_gate_attribution(
        workflow="ObraSignal Quality",
        workflow_path=".github/workflows/quality.yml",
        changed_paths={"engineering_ops.py"},
        candidate_workflow_paths={".github/workflows/quality.yml"},
        path_filters=None,
        candidate_pr=407,
        run_trigger_pr=407,
    )
    assert attribution.state == "REQUIRED"


def test_extract_pull_request_paths_distinguishes_unfiltered_and_filtered():
    assert extract_pull_request_paths("name: Quality\non:\n  pull_request:\n  workflow_dispatch:\n") is None
    assert extract_pull_request_paths(
        "name: Ops\non:\n  pull_request:\n    paths:\n      - engineering_ops.py\n      - 'tests/**'\n"
    ) == ("engineering_ops.py", "tests/**")


def test_ambiguous_path_filter_parse_fails_closed():
    filters = extract_pull_request_paths("name: Ops\non:\n  pull_request:\n    paths: [engineering_ops.py]\n")
    assert filters is None or filters == ()
