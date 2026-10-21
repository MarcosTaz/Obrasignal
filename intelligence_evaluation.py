"""Repository-safe Opportunity Intelligence evaluation harness.

The corpus is synthetic and proves deterministic invariants only. It is not a
production-quality estimate, an ML holdout, or customer outcome evidence.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from opportunity_match_pipeline import RULE_VERSION, evaluate_row

DEFAULT_CORPUS = Path(__file__).with_name("tests") / "fixtures" / "intelligence_evaluation_v1.json"


def load_corpus(path: str | Path = DEFAULT_CORPUS) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def corpus_fingerprint(corpus: dict[str, Any]) -> str:
    canonical = json.dumps(corpus, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _profiles_by_case(corpus: dict[str, Any]) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for case in corpus.get("cases", []):
        if "profile" in case:
            profiles[case["id"]] = copy.deepcopy(case["profile"])
    return profiles


def _positive_company_evidence(result: dict[str, Any]) -> bool:
    capability = result.get("capability_evidence") or {}
    cpv = result.get("cpv_evidence") or {}
    return bool(capability.get("matched") or cpv.get("strength") == "STRONG")


def _evaluate_case(case: dict[str, Any], profiles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if "profile" in case:
        profile = copy.deepcopy(case["profile"])
    else:
        profile = copy.deepcopy(profiles[case["profile_ref"]])
    result = evaluate_row(copy.deepcopy(case["opportunity"]), profile=profile)
    return {
        "id": case["id"],
        "label": case["label"],
        "rationale": case["rationale"],
        "decision": result.get("decision"),
        "profile_score": result.get("profile_score"),
        "lot_score": result.get("lot_score"),
        "positive_company_evidence": _positive_company_evidence(result),
        "capability_status": (result.get("capability_evidence") or {}).get("status"),
        "cpv_strength": (result.get("cpv_evidence") or {}).get("strength"),
        "hard_blockers": list(result.get("hard_capability_blockers") or []),
        "commercial_rule_version": (result.get("commercial") or {}).get("rule_version"),
        "decision_rule_version": RULE_VERSION,
    }


def evaluate_corpus(corpus: dict[str, Any]) -> dict[str, Any]:
    """Evaluate qualitative expectations without manufacturing numeric targets."""
    profiles = _profiles_by_case(corpus)
    observations = [_evaluate_case(case, profiles) for case in corpus.get("cases", [])]
    by_id = {item["id"]: item for item in observations}
    violations: list[dict[str, Any]] = []
    known_debt: list[dict[str, Any]] = []

    for case in corpus.get("cases", []):
        observed = by_id[case["id"]]
        expected = case.get("expected") or {}
        debt_issue = expected.get("known_debt_issue")
        if debt_issue:
            known_debt.append({
                "case": case["id"],
                "issue": debt_issue,
                "observed_decision": observed["decision"],
                "positive_company_evidence": observed["positive_company_evidence"],
                "hard_blockers": observed["hard_blockers"],
            })

        if "positive_company_evidence" in expected and observed["positive_company_evidence"] != expected["positive_company_evidence"]:
            violations.append({"case": case["id"], "invariant": "positive_company_evidence", "expected": expected["positive_company_evidence"], "observed": observed["positive_company_evidence"]})
        if "hard_blocker" in expected and bool(observed["hard_blockers"]) != expected["hard_blocker"]:
            violations.append({"case": case["id"], "invariant": "hard_blocker", "expected": expected["hard_blocker"], "observed": bool(observed["hard_blockers"])})
        if expected.get("decision_in") and observed["decision"] not in expected["decision_in"]:
            violations.append({"case": case["id"], "invariant": "decision_in", "expected": expected["decision_in"], "observed": observed["decision"]})
        if expected.get("blocker_contains") and not any(expected["blocker_contains"] in blocker for blocker in observed["hard_blockers"]):
            violations.append({"case": case["id"], "invariant": "blocker_contains", "expected": expected["blocker_contains"], "observed": observed["hard_blockers"]})

    for pair in corpus.get("pairwise", []):
        higher = by_id[pair["higher"]]
        lower = by_id[pair["lower"]]
        field = pair["field"]
        if not (higher[field] > lower[field]):
            violations.append({
                "case": f"{pair['higher']}>{pair['lower']}",
                "invariant": f"pairwise:{field}",
                "expected": "higher > lower",
                "observed": {"higher": higher[field], "lower": lower[field]},
            })

    label_counts: dict[str, int] = {}
    for item in observations:
        label_counts[item["label"]] = label_counts.get(item["label"], 0) + 1

    return {
        "corpus_version": corpus.get("version"),
        "corpus_fingerprint": corpus_fingerprint(corpus),
        "decision_rule_version": RULE_VERSION,
        "dataset_size": len(observations),
        "label_counts": label_counts,
        "observations": observations,
        "violations": violations,
        "known_debt": known_debt,
        "limitations": [
            "synthetic corpus; no production customer data",
            "qualitative invariant evidence only; not market precision/recall",
            "known-debt cases remain visible rather than being normalized into a green baseline",
        ],
    }


def run(path: str | Path = DEFAULT_CORPUS) -> dict[str, Any]:
    return evaluate_corpus(load_corpus(path))


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True, indent=2))
