from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


class VerificationPlan(NamedTuple):
    cwd: str
    argv: tuple[str, ...]
    evidence_code: str


PLANS: dict[tuple[str, str], VerificationPlan] = {
    ("guaranteerelease", "verify:source-tests"): VerificationPlan(
        cwd=".", argv=("__GUARANTEE_NODE_TESTS__",), evidence_code="GUARANTEERELEASE_SOURCE_TESTS_GREEN"
    ),
    ("royaltyrecover", "verify:source-tests"): VerificationPlan(
        cwd="factories/royaltyrecover",
        argv=(sys.executable, "-m", "unittest", "-v"),
        evidence_code="ROYALTYRECOVER_SOURCE_TESTS_GREEN",
    ),
}


def verification_plan(app_id: str, task: str, root: Path = Path(".")) -> tuple[Path, tuple[str, ...], str] | None:
    plan = PLANS.get((app_id, task))
    if plan is None:
        return None
    cwd = root / plan.cwd
    if app_id == "guaranteerelease":
        tests = tuple(str(path) for path in sorted((root / "ventures/guaranteerelease").glob("*.test.mjs")))
        if not tests:
            return None
        return root, ("node", "--test", *tests), plan.evidence_code
    return cwd, plan.argv, plan.evidence_code


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return 2
    app_id = str(request.get("app_id") or "")
    task = str(request.get("task") or "")
    plan = verification_plan(app_id, task)
    if plan is None:
        print(json.dumps({
            "status": "BLOCKED",
            "evidence": {"task_state": "NOT_ALLOWLISTED", "evidence_codes": ["VERIFIED_SOURCE_AGENT_SCOPE_REJECTED"]},
            "next_active": task,
            "blockers": ["verified_source_task_not_allowlisted_or_source_missing"],
            "resume_at": task,
        }))
        return 0

    cwd, argv, evidence_code = plan
    if not cwd.is_dir():
        print(json.dumps({
            "status": "WAIT",
            "evidence": {"task_state": "SOURCE_PATH_MISSING", "evidence_codes": ["VERIFIED_SOURCE_PATH_MISSING"]},
            "next_active": task,
            "blockers": ["verified_source_path_missing"],
            "resume_at": task,
        }))
        return 0

    try:
        completed = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=1200, check=False)
    except (OSError, subprocess.SubprocessError):
        print(json.dumps({
            "status": "ERROR",
            "evidence": {"test_state": "UNKNOWN", "task_state": "VERIFY_UNAVAILABLE", "evidence_codes": ["VERIFIED_SOURCE_TEST_RUNNER_UNAVAILABLE"]},
            "next_active": task,
            "blockers": ["verified_source_test_runner_unavailable"],
            "resume_at": task,
            "error": {"type": "VERIFIED_SOURCE_TEST_RUNNER_UNAVAILABLE"},
        }))
        return 0

    if completed.returncode != 0:
        print(json.dumps({
            "status": "ERROR",
            "evidence": {"test_state": "FAIL", "task_state": "VERIFY_FAILED", "evidence_codes": ["VERIFIED_SOURCE_TEST_FAILURE"]},
            "next_active": task,
            "blockers": ["verified_source_tests_failed"],
            "resume_at": task,
            "error": {"type": "VERIFIED_SOURCE_TEST_FAILURE"},
        }))
        return 0

    print(json.dumps({
        "status": "DONE",
        "evidence": {"test_state": "PASS", "task_state": "VERIFIED", "evidence_codes": [evidence_code]},
        "next_active": "",
        "resume_at": "",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
