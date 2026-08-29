from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from factory_cloud.pilot_safe_evidence import load_evidence_manifest, passing_tokens
from factory_cloud.portfolio import load_portfolio

POLICY_PATH = Path(__file__).with_name("pilot_safe_policy.json")
EVIDENCE_DIR = Path(__file__).with_name("pilot_safe_evidence")
APPS_PATH = Path(__file__).with_name("apps.json")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


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


def verified_registered_source_head(factory_id: str, apps_path: str | Path = APPS_PATH) -> str | None:
    """Return the explicitly verified execution head used for certification.

    Execution source wins over canonical source because certification can safely
    evaluate an immutable candidate without changing canonical authority. A
    canonical head is accepted only when no execution source is present and the
    canonical source itself is explicitly verified. Invalid/missing heads fail
    closed to None.
    """
    data = json.loads(Path(apps_path).read_text(encoding="utf-8"))
    for app in data.get("applications", []):
        if str(app.get("app_id") or "") != factory_id:
            continue
        execution = app.get("execution_source") or {}
        execution_head = str(execution.get("head") or "").strip()
        if execution.get("verified") is True and _SHA_RE.fullmatch(execution_head):
            return execution_head
        source = app.get("source_truth") or {}
        canonical_head = str(source.get("canonical_head") or "").strip()
        if source.get("verified") is True and _SHA_RE.fullmatch(canonical_head):
            return canonical_head
        return None
    return None


def assess_manifest(
    path: str | Path,
    policy: dict | None = None,
    *,
    apps_path: str | Path = APPS_PATH,
) -> dict:
    manifest = load_evidence_manifest(path)
    tokens = passing_tokens(manifest)
    declared_head = str(manifest["exact_source_head"])
    registered_head = verified_registered_source_head(manifest["factory_id"], apps_path)
    source_bound = declared_head == registered_head and registered_head is not None

    # A manifest may record source evidence, but it cannot earn PS9 when its top-level
    # source SHA is stale, unregistered, or not explicitly verified in app authority.
    if "exact_source_head" in tokens and not source_bound:
        tokens.remove("exact_source_head")

    result = assess(manifest["factory_id"], tokens, policy=policy)
    result["exact_source_head"] = declared_head
    result["registered_source_head"] = registered_head
    result["exact_source_bound"] = source_bound
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
