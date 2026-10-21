"""Fail-closed audit for Customer Journey, First Value & Outcome Integrity.

This module validates composition metadata only. It never promotes specialist-owner
truth and never converts missing evidence into a successful customer outcome.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

FACTORY_TITLE = "Customer Journey, First Value & Outcome Integrity"
REQUIRED_EDGE_FIELDS = {
    "STEP",
    "CUSTOMER_INTENT",
    "ENTRY_CONDITION",
    "OWNER",
    "INPUT",
    "EXPECTED_CUSTOMER_TRUTH",
    "ACTION_AVAILABLE",
    "NEXT_STEP",
    "FAILURE_MODE",
    "RECOVERY",
    "TENANT_BOUNDARY",
    "SOURCE_DEPENDENCY",
    "CURRENT_TEST",
    "CURRENT_SHA",
    "STATUS",
    "EVIDENCE",
}
FAIL_CLOSED_STATUSES = {"BROKEN", "DISCOVERED_UNKNOWN", "STALE", "PREBUILD", "EXTERNAL_GOLDEN_ONLY"}
EXTERNAL_WAIT_BOUNDARIES = {
    "GOLDEN",
    "REAL_DEVICE_GOLDEN",
    "PROVIDER",
    "PRODUCTION_EVIDENCE",
    "CUSTOMER_EVIDENCE",
    "FOUNDER_AUTHORIZATION",
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _load_json(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_registry(path: str | Path = "customer_journey_registry.json") -> dict:
    return _load_json(path)


def load_stack(path: str | Path = "customer_journey_stack.json") -> dict:
    return _load_json(path)


def validate_registry(registry: dict) -> list[str]:
    errors: list[str] = []
    if registry.get("factory_title") != FACTORY_TITLE:
        errors.append("factory_title must remain canonical and exact")

    canonical_sha = registry.get("canonical_main_sha")
    if not isinstance(canonical_sha, str) or not SHA_RE.fullmatch(canonical_sha):
        errors.append("canonical_main_sha must be an exact 40-character lowercase SHA")

    allowed = registry.get("allowed_statuses")
    if not isinstance(allowed, list) or not allowed or len(set(allowed)) != len(allowed):
        errors.append("allowed_statuses must be a unique non-empty list")
        allowed_set: set[str] = set()
    else:
        allowed_set = set(allowed)
        forbidden = {"GREEN", "SUCCESS", "DONE", "PASS"} & allowed_set
        if forbidden:
            errors.append(f"subsystem status aliases are forbidden journey states: {sorted(forbidden)}")

    edges = registry.get("edges")
    if not isinstance(edges, list) or not edges:
        return errors + ["edges must be a non-empty list"]

    seen: set[str] = set()
    by_step: dict[str, dict] = {}
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(f"edge[{index}] must be an object")
            continue
        missing = REQUIRED_EDGE_FIELDS - set(edge)
        if missing:
            errors.append(f"edge[{index}] missing fields: {sorted(missing)}")
            continue

        step = edge["STEP"]
        if not isinstance(step, str) or not step.strip():
            errors.append(f"edge[{index}] STEP must be non-empty")
            continue
        if step in seen:
            errors.append(f"duplicate STEP: {step}")
        seen.add(step)
        by_step[step] = edge

        status = edge["STATUS"]
        if status not in allowed_set:
            errors.append(f"{step}: unknown STATUS {status!r}")
        if edge["CURRENT_SHA"] != canonical_sha:
            errors.append(f"{step}: CURRENT_SHA must describe the canonical main being classified")

        for field in ("INPUT", "ACTION_AVAILABLE", "SOURCE_DEPENDENCY", "CURRENT_TEST", "EVIDENCE"):
            if not isinstance(edge[field], list):
                errors.append(f"{step}: {field} must be a list")
        for field in (
            "CUSTOMER_INTENT",
            "ENTRY_CONDITION",
            "OWNER",
            "EXPECTED_CUSTOMER_TRUTH",
            "NEXT_STEP",
            "FAILURE_MODE",
            "RECOVERY",
            "TENANT_BOUNDARY",
        ):
            if not isinstance(edge[field], str) or not edge[field].strip():
                errors.append(f"{step}: {field} must be a non-empty string")

        if status == "PROVEN":
            if not edge["CURRENT_TEST"] or not edge["EVIDENCE"]:
                errors.append(f"{step}: PROVEN requires explicit executable evidence")
            if any("no canonical" in str(item).lower() for item in edge["CURRENT_TEST"]):
                errors.append(f"{step}: PROVEN cannot coexist with missing canonical evidence")

        if status in {"BROKEN", "PREBUILD"} and edge.get("BLOCKER") and not str(edge.get("REOPEN_CONDITION") or "").strip():
            errors.append(f"{step}: blocked {status} requires REOPEN_CONDITION")

    # Factory-specific truth guards. These deliberately constrain claims rather
    # than deciding specialist semantics.
    zero = by_step.get("RADAR_ZERO_STATE")
    if zero:
        truth = zero["EXPECTED_CUSTOMER_TRUTH"].upper()
        if "ZERO" not in truth or "MARKET" not in truth or "UNKNOWN" not in truth:
            errors.append("RADAR_ZERO_STATE must explicitly preserve zero-market/UNKNOWN distinction")
        if zero["STATUS"] == "PROVEN" and any("non-canonical" in str(item).lower() for item in zero["EVIDENCE"]):
            errors.append("RADAR_ZERO_STATE cannot be PROVEN from non-canonical integration evidence")

    first_value = by_step.get("FIRST_VALUE")
    if first_value and first_value["STATUS"] == "PROVEN":
        if zero and zero["STATUS"] in FAIL_CLOSED_STATUSES:
            errors.append("FIRST_VALUE cannot be PROVEN while RADAR_ZERO_STATE is unresolved on canonical main")
        if not first_value["CURRENT_TEST"]:
            errors.append("FIRST_VALUE PROVEN requires a deterministic canonical journey acceptance test")

    repeat_value = by_step.get("REPEAT_VALUE")
    if repeat_value and repeat_value["STATUS"] == "PROVEN" and not repeat_value["ACTION_AVAILABLE"]:
        errors.append("REPEAT_VALUE PROVEN requires a customer action or continuation path")

    # Avoid metric theater in this evidence registry.
    forbidden_top_level = {"score", "percentage", "overall_score", "journey_score", "completion_percent"}
    present = forbidden_top_level & set(registry)
    if present:
        errors.append(f"aggregate journey percentages/scores are forbidden: {sorted(present)}")

    return errors


def validate_stack(stack: dict, registry: dict) -> list[str]:
    errors: list[str] = []
    if stack.get("factory_title") != FACTORY_TITLE:
        errors.append("stack factory_title must remain canonical and exact")
    if stack.get("canonical_main_sha") != registry.get("canonical_main_sha"):
        errors.append("stack canonical_main_sha must match journey registry exact head")

    for section in ("ACTIVE", "NEXT", "WAIT"):
        value = stack.get(section)
        if not isinstance(value, list):
            errors.append(f"stack {section} must be a list")

    waits = stack.get("WAIT") if isinstance(stack.get("WAIT"), list) else []
    for index, item in enumerate(waits):
        if not isinstance(item, dict):
            errors.append(f"WAIT[{index}] must be an object")
            continue
        for field in ("step", "boundary", "reason", "reopen_condition"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"WAIT[{index}] requires non-empty {field}")
        if item.get("boundary") not in EXTERNAL_WAIT_BOUNDARIES:
            errors.append(f"WAIT[{index}] boundary must be a genuine external boundary")

    # EXTERNAL_GOLDEN_ONLY edges must be represented by a reopenable WAIT item.
    external_steps = {
        edge.get("STEP")
        for edge in registry.get("edges", [])
        if isinstance(edge, dict) and edge.get("STATUS") == "EXTERNAL_GOLDEN_ONLY"
    }
    wait_steps = {item.get("step") for item in waits if isinstance(item, dict)}
    missing_waits = external_steps - wait_steps
    if missing_waits:
        errors.append(f"EXTERNAL_GOLDEN_ONLY edges missing WAIT reopen contract: {sorted(missing_waits)}")

    return errors


def status_counts(registry: dict) -> dict[str, int]:
    return dict(sorted(Counter(edge["STATUS"] for edge in registry.get("edges", []) if isinstance(edge, dict) and "STATUS" in edge).items()))


def critical_edges(registry: dict) -> list[dict[str, str]]:
    result = []
    for edge in registry.get("edges", []):
        if not isinstance(edge, dict) or edge.get("STATUS") not in FAIL_CLOSED_STATUSES:
            continue
        result.append({
            "step": str(edge.get("STEP")),
            "status": str(edge.get("STATUS")),
            "owner": str(edge.get("OWNER")),
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", nargs="?", default="customer_journey_registry.json")
    parser.add_argument("--stack", default="customer_journey_stack.json")
    args = parser.parse_args()
    registry = load_registry(args.registry)
    stack = load_stack(args.stack)
    errors = validate_registry(registry) + validate_stack(stack, registry)
    payload = {
        "ok": not errors,
        "factory_title": registry.get("factory_title"),
        "canonical_main_sha": registry.get("canonical_main_sha"),
        "status_counts": status_counts(registry),
        "critical_edges": critical_edges(registry),
        "wait": stack.get("WAIT", []),
        "errors": errors,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
