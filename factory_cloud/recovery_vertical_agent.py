from __future__ import annotations

import json
import subprocess
import sys

COMMON_TESTS = (
    "tests/test_factory_cloud_vertical_consumers.py",
    "tests/test_factory_cloud_assurance_store.py",
    "tests/test_factory_cloud_vertical_runtime.py",
    "tests/test_factory_cloud_assurance_ops.py",
    "tests/test_factory_cloud_operation_audit.py",
    "tests/test_factory_cloud_recovery_primitives.py",
    "tests/test_factory_cloud_recovery_index.py",
    "tests/test_factory_cloud_fee_lineage.py",
    "tests/test_factory_cloud_pilot_readiness.py",
    "tests/test_vertical_application_services.py",
    "tests/test_vertical_end_to_end_outcomes.py",
    "tests/test_vertical_release_contracts.py",
    "tests/test_vertical_pilot_contracts.py",
    "tests/test_vertical_web_apis.py",
)
INDUSTRIAL_TESTS = COMMON_TESTS + (
    "tests/test_industrial_claims_service.py",
    "tests/test_industrial_claims_recovery_cap.py",
    "tests/test_industrial_claims_replay_integrity.py",
    "tests/test_industrial_claims_atomic_persistence.py",
    "tests/test_industrial_claims_document_privacy.py",
    "tests/test_industrial_claims_synthetic_oracle.py",
    "tests/test_industrial_claims_package.py",
    "tests/test_industrial_claims_pilot_contract.py",
    "tests/test_industrial_claims_backup_restore.py",
    "tests/test_industrial_claims_web.py",
    "tests/test_industrial_claims_console.py",
    "tests/test_industrial_claims_queue.py",
)
APP_TESTS = {
    "aviation-lease-entitlement-recovery": COMMON_TESTS,
    "contractcredit": COMMON_TESTS,
    "industrial-claims": INDUSTRIAL_TESTS,
}
ALLOWED_TASKS = {"verify:service", "verify:shared-contracts"}


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return 2
    app_id = str(request.get("app_id") or "")
    task = str(request.get("task") or "")
    if app_id not in APP_TESTS or task not in ALLOWED_TASKS:
        print(json.dumps({
            "status": "BLOCKED",
            "evidence": {"task_state": "NOT_ALLOWLISTED", "evidence_codes": ["RECOVERY_AGENT_SCOPE_REJECTED"]},
            "next_active": task,
            "blockers": ["recovery_agent_task_not_allowlisted"],
            "resume_at": task,
        }))
        return 0

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *APP_TESTS[app_id]],
        text=True,
        capture_output=True,
        timeout=900,
        check=False,
    )
    if completed.returncode != 0:
        print(json.dumps({
            "status": "ERROR",
            "evidence": {"test_state": "FAIL", "task_state": "VERIFY_FAILED", "evidence_codes": ["RECOVERY_VERTICAL_TEST_FAILURE"]},
            "next_active": task,
            "blockers": ["recovery_vertical_tests_failed"],
            "resume_at": task,
            "error": {"type": "RECOVERY_VERTICAL_TEST_FAILURE"},
        }))
        return 0

    next_active = "verify:shared-contracts" if task == "verify:service" else ""
    print(json.dumps({
        "status": "DONE",
        "evidence": {"test_state": "PASS", "task_state": "VERIFIED", "evidence_codes": ["RECOVERY_VERTICAL_TESTS_GREEN"]},
        "next_active": next_active,
        "resume_at": next_active,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
