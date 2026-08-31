"""Observation-only GitHub Actions / CI toolchain inventory.

This module parses repository workflow text without executing workflows or reading
secret values. It records references, workflow/job permissions, secret names,
runner/toolchain declarations and known pin candidates already proven by Security
#248. It does not mutate workflows and is not an Actions authority.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKFLOWS = ROOT / ".github" / "workflows"

PROVEN_248_PINS = {
    ("actions/checkout", "v4"): "11d5960a326750d5838078e36cf38b85af677262",
    ("actions/checkout", "v5"): "fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09",
    ("actions/setup-python", "v5"): "a26af69be951a213d495a4c3e4e4022e16d87065",
    ("actions/setup-node", "v4"): "49933ea5288caeca8642d1e84afbd3f7d6820020",
    ("actions/setup-node", "v6"): "249970729cb0ef3589644e2896645e5dc5ba9c38",
    ("actions/upload-artifact", "v4"): "ea165f8d65b6e75b540449e92b4886f43607fa02",
    ("actions/configure-pages", "v5"): "983d7736d9b0ae728b81ab479565c72886d7745b",
    ("actions/upload-pages-artifact", "v3"): "56afc609e74202658d3ffba0e8f6dda462b719fa",
    ("actions/deploy-pages", "v4"): "d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e",
    ("expo/expo-github-action", "v8"): "c7b66a9c327a43a8fa7c0158e7f30d6040d2481e",
}

OWNER_BY_WORKFLOW = {
    "auth-diagnostic.yml": "Auth",
    "auth-verifier-live.yml": "Auth",
    "authenticated-e2e.yml": "Auth/Release",
    "canadabuys_live.yml": "Sources/CanadaBuys",
    "eas-preview.yml": "Release/Mobile",
    "eas-production.yml": "Release/Mobile",
    "mobile-release-preflight.yml": "Release/Mobile",
    "production-smoke.yml": "Release/Readiness",
    "quality.yml": "Quality",
    "us_sam_live.yml": "Sources/US-SAM",
    "web-preview.yml": "Web/Release",
    "supply-chain-resolution.yml": "Dependency Factory",
}

WRITE_KEYS = {"actions", "checks", "contents", "deployments", "id-token", "packages", "pages", "pull-requests", "security-events"}


def _pin_type(reference: str) -> str:
    if re.fullmatch(r"[0-9a-fA-F]{40}", reference):
        return "COMMIT_PINNED"
    if re.fullmatch(r"v?\d+(?:\.\d+){0,2}", reference) or reference == "latest":
        return "MUTABLE_TAG"
    if reference:
        return "BRANCH_OR_OTHER_MUTABLE_REF"
    return "UNKNOWN"


def _top_permissions(text: str) -> dict[str, str]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line == "permissions:":
            result = {}
            for candidate in lines[index + 1 :]:
                if not candidate.startswith("  ") or candidate.startswith("    "):
                    break
                if ":" in candidate:
                    key, value = candidate.strip().split(":", 1)
                    result[key] = value.strip()
            return result
    return {"__authority__": "IMPLICIT_DEFAULT"}


def _job_permission_map(lines: list[str]) -> dict[str, dict[str, str]]:
    """Record explicit job-level overrides so workflow-read cannot hide job-write."""
    result: dict[str, dict[str, str]] = {}
    in_jobs = False
    current = None
    index = 0
    while index < len(lines):
        line = lines[index]
        if line == "jobs:":
            in_jobs = True
            index += 1
            continue
        if in_jobs and re.fullmatch(r"  [A-Za-z0-9_-]+:", line):
            current = line.strip()[:-1]
            index += 1
            continue
        if in_jobs and current and line == "    permissions:":
            permissions = {}
            index += 1
            while index < len(lines):
                candidate = lines[index]
                if not candidate.startswith("      ") or candidate.startswith("        "):
                    break
                if ":" in candidate:
                    key, value = candidate.strip().split(":", 1)
                    permissions[key] = value.strip()
                index += 1
            result[current] = permissions
            continue
        index += 1
    return result


def _write_permissions(permissions: dict[str, str]) -> list[str]:
    if permissions.get("__authority__") == "IMPLICIT_DEFAULT":
        return ["UNKNOWN_DEFAULT"]
    return sorted(
        f"{key}:{value}" for key, value in permissions.items()
        if key in WRITE_KEYS and value == "write"
    )


def _job_for_line(lines: list[str], target: int) -> str:
    in_jobs = False
    current = "UNKNOWN"
    for line in lines[: target + 1]:
        if line == "jobs:":
            in_jobs = True
            continue
        if in_jobs and re.fullmatch(r"  [A-Za-z0-9_-]+:", line):
            current = line.strip()[:-1]
    return current


def _network_role(action: str) -> str:
    if action == "actions/checkout":
        return "SOURCE_FETCH"
    if action.startswith("actions/setup-"):
        return "TOOLCHAIN_SETUP"
    if "upload" in action:
        return "ARTIFACT_UPLOAD"
    if "deploy" in action or "configure-pages" in action:
        return "DEPLOYMENT"
    if action == "expo/expo-github-action":
        return "REMOTE_BUILD_AUTH"
    return "THIRD_PARTY_EXECUTION"


def inventory() -> dict:
    records = []
    workflow_records = []
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        permissions = _top_permissions(text)
        job_permissions = _job_permission_map(lines)
        secret_names = sorted(set(re.findall(r"secrets\.([A-Za-z0-9_]+)", text)))
        runner_values = sorted(set(re.findall(r"runs-on:\s*([^\n#]+)", text)))
        node_versions = sorted(set(re.findall(r"node-version:\s*['\"]?([^'\"\n#]+)", text)))
        python_versions = sorted(set(re.findall(r"python-version:\s*['\"]?([^'\"\n#]+)", text)))
        eas_versions = sorted(set(re.findall(r"eas-version:\s*['\"]?([^'\"\n#]+)", text)))
        workflow_records.append({
            "workflow": path.name,
            "expected_owner": OWNER_BY_WORKFLOW.get(path.name, "UNKNOWN"),
            "permissions": permissions,
            "write_permissions": _write_permissions(permissions),
            "job_permissions": job_permissions,
            "job_write_permissions": {job: _write_permissions(value) for job, value in job_permissions.items()},
            "secret_names": secret_names,
            "runner": runner_values or ["UNKNOWN"],
            "node_versions": node_versions,
            "python_versions": python_versions,
            "eas_versions": eas_versions,
        })
        for index, line in enumerate(lines):
            match = re.search(r"\buses:\s*([^\s#]+)", line)
            if not match:
                continue
            spec = match.group(1)
            action, sep, reference = spec.rpartition("@")
            if not sep:
                action, reference = spec, ""
            pin_type = _pin_type(reference)
            major_key = reference if pin_type == "MUTABLE_TAG" else None
            proven = PROVEN_248_PINS.get((action, major_key)) if major_key else None
            job = _job_for_line(lines, index)
            effective_permissions = job_permissions.get(job, permissions)
            effective_writes = _write_permissions(effective_permissions)
            critical = bool(secret_names or effective_writes or action == "expo/expo-github-action" or "deploy" in action)
            records.append({
                "workflow": path.name,
                "job": job,
                "action": action,
                "reference": reference,
                "pin_type": pin_type,
                "expected_owner": OWNER_BY_WORKFLOW.get(path.name, "UNKNOWN"),
                "permissions": effective_permissions,
                "write_permissions": effective_writes,
                "secret_names": secret_names,
                "network_role": _network_role(action),
                "criticality": "CRITICAL" if critical else "HIGH",
                "proven_248_pin_candidate": proven,
            })
    return {
        "schema": "obrasignal-actions-inventory.v1",
        "authority": "observation_only",
        "actions": records,
        "workflows": workflow_records,
    }


def main() -> None:
    print(json.dumps(inventory(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
