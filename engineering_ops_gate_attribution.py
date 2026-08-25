"""Fail-closed CI gate attribution for Engineering Operations.

This module classifies whether an observed workflow result is actually required
for a candidate owner. It never changes domain truth or authorization.
"""

from __future__ import annotations

import fnmatch
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Sequence

ATTRIBUTION_STATES = (
    "REQUIRED",
    "INCIDENTALLY_TRIGGERED",
    "NOT_APPLICABLE",
    "REQUIRED_NOT_RUN",
    "NEEDS_RECHECK",
)

OWNER_GATE_STATES = ("GREEN", "RED", "NEEDS_RECHECK")


@dataclass(frozen=True)
class GateAttribution:
    workflow: str
    state: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _matches_any_path(changed_paths: Iterable[str], filters: Sequence[str]) -> bool:
    paths = tuple(str(path) for path in changed_paths)
    return any(fnmatch.fnmatch(path, pattern) for path in paths for pattern in filters)


def extract_pull_request_paths(workflow_text: str) -> tuple[str, ...] | None:
    """Extract simple GitHub Actions pull_request.paths entries without YAML deps.

    Returns None when pull_request has no paths restriction. The parser is narrow
    by design: ambiguous constructs fail closed by returning an empty tuple,
    which callers treat as NEEDS_RECHECK rather than applicability proof.
    """
    lines = workflow_text.splitlines()
    in_pull_request = False
    pull_indent = -1
    in_paths = False
    paths_indent = -1
    found_paths_key = False
    values: list[str] = []

    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        if stripped.startswith("pull_request:"):
            in_pull_request = True
            pull_indent = indent
            in_paths = False
            continue
        if in_pull_request and indent <= pull_indent and not stripped.startswith("pull_request:"):
            break
        if not in_pull_request:
            continue
        if stripped == "paths:":
            found_paths_key = True
            in_paths = True
            paths_indent = indent
            continue
        if in_paths:
            if indent <= paths_indent:
                in_paths = False
                continue
            if stripped.startswith("-"):
                value = stripped[1:].strip().strip("'\"")
                if value:
                    values.append(value)
            else:
                return ()

    if not found_paths_key:
        return None
    return tuple(values)


def classify_gate_attribution(
    *,
    workflow: str,
    workflow_path: str | None,
    changed_paths: Iterable[str],
    explicit_required_workflows: Iterable[str] = (),
    candidate_workflow_paths: Iterable[str] = (),
    path_filters: Sequence[str] | None = None,
    run_trigger_pr: int | None = None,
    candidate_pr: int | None = None,
) -> GateAttribution:
    """Classify a gate without interpreting the gate's pass/fail result.

    Precedence is deliberately fail-closed:
    1. an explicit owner/Assembly requirement makes the gate REQUIRED;
    2. a run triggered for a different PR, whose workflow is absent from the
       candidate tree, is incidental to this candidate;
    3. a present unfiltered pull_request workflow is REQUIRED;
    4. a present workflow with deterministic path filters is REQUIRED only when
       the candidate delta matches those filters, otherwise NOT_APPLICABLE;
    5. missing/ambiguous information is NEEDS_RECHECK.
    """
    required = {str(name) for name in explicit_required_workflows}
    candidate_workflows = {str(path) for path in candidate_workflow_paths}

    if workflow in required:
        return GateAttribution(workflow, "REQUIRED", "explicit candidate gate contract")

    if (
        run_trigger_pr is not None
        and candidate_pr is not None
        and run_trigger_pr != candidate_pr
        and workflow_path
        and workflow_path not in candidate_workflows
    ):
        return GateAttribution(
            workflow,
            "INCIDENTALLY_TRIGGERED",
            "run belongs to another PR context and workflow is absent from candidate tree",
        )

    if workflow_path and workflow_path in candidate_workflows:
        if path_filters is None:
            return GateAttribution(
                workflow,
                "REQUIRED",
                "workflow is present in candidate tree with unfiltered pull_request contract",
            )
        if len(path_filters) == 0:
            return GateAttribution(
                workflow,
                "NEEDS_RECHECK",
                "workflow path filter contract could not be parsed safely",
            )
        if not _matches_any_path(changed_paths, path_filters):
            return GateAttribution(
                workflow,
                "NOT_APPLICABLE",
                "candidate delta does not match workflow pull_request path filters",
            )
        return GateAttribution(
            workflow,
            "REQUIRED",
            "candidate delta matches repository workflow trigger contract",
        )

    return GateAttribution(
        workflow,
        "NEEDS_RECHECK",
        "insufficient repository evidence to attribute gate safely",
    )


def complete_required_gates(
    *,
    required_workflows: Iterable[str],
    observed_gate_states: Mapping[str, str],
) -> list[GateAttribution]:
    """Emit REQUIRED_NOT_RUN for required gates lacking exact-head execution."""
    result: list[GateAttribution] = []
    for workflow in sorted({str(name) for name in required_workflows}):
        state = observed_gate_states.get(workflow)
        if state in {None, "NOT_RUN", "HISTORICAL"}:
            result.append(
                GateAttribution(
                    workflow,
                    "REQUIRED_NOT_RUN",
                    "required gate has no exact-head completed execution",
                )
            )
        else:
            result.append(GateAttribution(workflow, "REQUIRED", "required gate observed"))
    return result


def evaluate_owner_gate_state(
    gates: Iterable[Mapping[str, str]],
) -> tuple[str, str]:
    """Evaluate owner CI truth after attribution.

    Incidentally-triggered and NOT_APPLICABLE failures do not make an owner RED.
    Required failures do. Unknown attribution and required-not-run never become
    GREEN.
    """
    saw_required = False
    for gate in gates:
        attribution = str(gate.get("attribution") or "NEEDS_RECHECK")
        gate_state = str(gate.get("gate_state") or "UNKNOWN")
        workflow = str(gate.get("workflow") or "UNKNOWN")

        if attribution in {"NEEDS_RECHECK", "REQUIRED_NOT_RUN"}:
            return "NEEDS_RECHECK", f"{workflow}: {attribution}"
        if attribution != "REQUIRED":
            continue
        saw_required = True
        if gate_state == "FAIL":
            return "RED", f"{workflow}: required gate failed"
        if gate_state != "PASS":
            return "NEEDS_RECHECK", f"{workflow}: required gate is {gate_state}"

    if not saw_required:
        return "NEEDS_RECHECK", "no required gate contract proven"
    return "GREEN", "all required exact-head gates passed"
