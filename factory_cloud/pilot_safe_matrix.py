from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from factory_cloud.pilot_safe_evidence import load_evidence_manifest, passing_tokens
from factory_cloud.portfolio import load_portfolio

POLICY_PATH = Path(__file__).with_name("pilot_safe_policy.json")
EVIDENCE_DIR = Path(__file__).with_name("pilot_safe_evidence")


def load_policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def required_evidence(policy: dict | None = None) -> set[str]:
    policy = policy or load_policy()
    return {
        str(item)
        for gate in policy["gates"]
        for item in gate["required_evidence"]
    }


def assess(factory_id: str, evidence: Iterable[str], policy: dict | None = None) -> dict:
    policy = policy or load_policy()
    observed = {str(item) for item in evidence}
    forbidden = sorted(observed & set(policy["forbidden_as_pre_customer_proof"]))
    gates = {}
    missing = set()
    for gate in policy["gates"]:
        absent = sorted(set(gate["required_evidence"]) - observed)
        gates[gate["id"]] = "PASS" if not absent else "BLOCKED"
        missing.update(absent)
    safe = all(value == "PASS" for value in gates.values()) and not forbidden
    return {
        "factory_id": factory_id,
        "classification": "PILOT_SAFE" if safe else "NOT_PILOT_SAFE",
        "gates": gates,
        "missing_evidence": sorted(missing),
        "forbidden_evidence_seen": forbidden,
    }


def assess_manifest(path: str | Path, policy: dict | None = None) -> dict:
    manifest = load_evidence_manifest(path)
    result = assess(manifest["factory_id"], passing_tokens(manifest), policy=policy)
    result["exact_source_head"] = manifest["exact_source_head"]
    result["manifest_path"] = str(path)
    return result


def evidence_manifest_path(factory_id: str) -> Path:
    return EVIDENCE_DIR / f"{factory_id}.json"


def portfolio_matrix(evidence_by_factory: dict[str, Iterable[str]] | None = None) -> list[dict]:
    """Assess every portfolio entry, including unregistered/transitional Factories."""
    evidence_by_factory = evidence_by_factory or {}
    portfolio = load_portfolio()
    rows = []
    for factory in portfolio["portfolio"]:
        factory_id = factory["id"]
        manifest_path = evidence_manifest_path(factory_id)
        if factory_id in evidence_by_factory:
            row = assess(factory_id, evidence_by_factory[factory_id])
        elif manifest_path.exists():
            row = assess_manifest(manifest_path)
        else:
            row = assess(factory_id, ())
        row["source_status"] = factory["source_status"]
        row["maturity"] = factory["maturity"]
        rows.append(row)
    return rows
