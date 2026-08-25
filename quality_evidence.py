from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


class EvidenceContractError(ValueError):
    """Raised when the evidence manifest itself is malformed."""


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value.strip()):
        raise EvidenceContractError(f"{field} must be a full 40-character git SHA")
    return value.strip().lower()


@dataclass(frozen=True)
class RunEvidence:
    workflow: str
    head_sha: str
    status: str
    conclusion: str | None
    run_id: int | None = None
    tree_sha: str | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "RunEvidence":
        workflow = raw.get("workflow")
        if not isinstance(workflow, str) or not workflow.strip():
            raise EvidenceContractError("runs[].workflow must be a non-empty string")

        run_id = raw.get("run_id")
        if run_id is not None and (not isinstance(run_id, int) or run_id <= 0):
            raise EvidenceContractError("runs[].run_id must be a positive integer when present")

        status = raw.get("status")
        if not isinstance(status, str) or not status.strip():
            raise EvidenceContractError("runs[].status must be a non-empty string")

        conclusion = raw.get("conclusion")
        if conclusion is not None and not isinstance(conclusion, str):
            raise EvidenceContractError("runs[].conclusion must be a string or null")

        tree_sha = raw.get("tree_sha")
        return cls(
            workflow=workflow.strip(),
            head_sha=_sha(raw.get("head_sha"), "runs[].head_sha"),
            status=status.strip().lower(),
            conclusion=conclusion.strip().lower() if isinstance(conclusion, str) else None,
            run_id=run_id,
            tree_sha=_sha(tree_sha, "runs[].tree_sha") if tree_sha is not None else None,
        )


def _issue(code: str, subject: str, detail: str) -> dict[str, str]:
    return {"code": code, "subject": subject, "detail": detail}


def _latest_run(runs: Sequence[RunEvidence]) -> RunEvidence | None:
    if not runs:
        return None
    if len(runs) == 1:
        return runs[0]
    if any(run.run_id is None for run in runs):
        raise EvidenceContractError(
            "multiple runs for one workflow require run_id so the newest evidence is unambiguous"
        )
    return max(runs, key=lambda run: int(run.run_id or 0))


def audit_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless every required proof belongs to the exact current candidate.

    The manifest is intentionally explicit. It does not infer GREEN from prose, ancestor
    commits, skipped/path-filtered workflows, or owner evidence captured before owner drift.
    """

    candidate_sha = _sha(manifest.get("candidate_sha"), "candidate_sha")
    candidate_tree_sha = _sha(manifest.get("candidate_tree_sha"), "candidate_tree_sha")
    base_sha = _sha(manifest.get("base_sha"), "base_sha")
    current_main_sha = _sha(manifest.get("current_main_sha"), "current_main_sha")

    required_workflows = manifest.get("required_workflows")
    if not isinstance(required_workflows, list) or not required_workflows:
        raise EvidenceContractError("required_workflows must be a non-empty list")
    if any(not isinstance(name, str) or not name.strip() for name in required_workflows):
        raise EvidenceContractError("required_workflows entries must be non-empty strings")
    if len(set(required_workflows)) != len(required_workflows):
        raise EvidenceContractError("required_workflows must not contain duplicates")

    raw_runs = manifest.get("runs", [])
    if not isinstance(raw_runs, list):
        raise EvidenceContractError("runs must be a list")
    runs = [RunEvidence.from_mapping(raw) for raw in raw_runs]

    issues: list[dict[str, str]] = []

    if base_sha != current_main_sha:
        issues.append(
            _issue(
                "STALE_MAIN",
                "main",
                f"candidate base {base_sha} does not equal current main {current_main_sha}",
            )
        )

    workflow_results: dict[str, str] = {}
    for raw_name in required_workflows:
        name = raw_name.strip()
        named_runs = [run for run in runs if run.workflow == name]
        exact_runs = [run for run in named_runs if run.head_sha == candidate_sha]
        exact = _latest_run(exact_runs)

        if exact is None:
            historical_success = any(
                run.status == "completed" and run.conclusion == "success" for run in named_runs
            )
            code = "HISTORICAL_GREEN" if historical_success else "NOT_RUN"
            detail = (
                "only successful historical evidence exists; exact candidate HEAD was not proven"
                if historical_success
                else "required workflow has no exact-head run"
            )
            workflow_results[name] = code
            issues.append(_issue(code, name, detail))
            continue

        if exact.tree_sha is not None and exact.tree_sha != candidate_tree_sha:
            workflow_results[name] = "WRONG_TREE"
            issues.append(
                _issue(
                    "WRONG_TREE",
                    name,
                    f"run tree {exact.tree_sha} does not equal candidate tree {candidate_tree_sha}",
                )
            )
            continue

        if exact.status != "completed":
            workflow_results[name] = "IN_PROGRESS"
            issues.append(
                _issue(
                    "IN_PROGRESS",
                    name,
                    f"exact-head run status is {exact.status!r}, not completed",
                )
            )
            continue

        if exact.conclusion == "skipped":
            workflow_results[name] = "SKIPPED"
            issues.append(
                _issue("SKIPPED", name, "required exact-head workflow concluded skipped")
            )
            continue

        if exact.conclusion != "success":
            workflow_results[name] = "RED"
            issues.append(
                _issue(
                    "RED",
                    name,
                    f"exact-head workflow conclusion is {exact.conclusion!r}, not success",
                )
            )
            continue

        workflow_results[name] = "GREEN"

    owner_inputs = manifest.get("owner_inputs", [])
    if not isinstance(owner_inputs, list):
        raise EvidenceContractError("owner_inputs must be a list")
    owner_results: dict[str, str] = {}
    for raw in owner_inputs:
        if not isinstance(raw, Mapping):
            raise EvidenceContractError("owner_inputs entries must be objects")
        owner = raw.get("owner")
        if not isinstance(owner, str) or not owner.strip():
            raise EvidenceContractError("owner_inputs[].owner must be a non-empty string")
        current_sha = _sha(raw.get("current_sha"), "owner_inputs[].current_sha")
        evidence_sha = _sha(raw.get("evidence_sha"), "owner_inputs[].evidence_sha")
        if current_sha != evidence_sha:
            owner_results[owner] = "OWNER_DRIFT"
            issues.append(
                _issue(
                    "OWNER_DRIFT",
                    owner,
                    f"evidence used {evidence_sha} but owner is now {current_sha}",
                )
            )
        else:
            owner_results[owner] = "CURRENT"

    return {
        "verdict": "GREEN" if not issues else "NOT_GREEN",
        "candidate_sha": candidate_sha,
        "candidate_tree_sha": candidate_tree_sha,
        "base_sha": base_sha,
        "current_main_sha": current_main_sha,
        "workflows": workflow_results,
        "owner_inputs": owner_results,
        "issues": issues,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed exact-head evidence validator for ObraSignal candidates"
    )
    parser.add_argument("manifest", type=Path, help="JSON evidence manifest")
    args = parser.parse_args(argv)

    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if not isinstance(manifest, Mapping):
            raise EvidenceContractError("manifest root must be a JSON object")
        result = audit_manifest(manifest)
    except (OSError, json.JSONDecodeError, EvidenceContractError) as exc:
        print(json.dumps({"verdict": "INVALID", "error": str(exc)}, sort_keys=True))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verdict"] == "GREEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
