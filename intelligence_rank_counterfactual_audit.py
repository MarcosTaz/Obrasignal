"""Controlled score→rank→Top-K impact audit with no production policy changes."""
from __future__ import annotations

import copy
from typing import Any

from intelligence_counterfactual_audit import base_opportunity, base_profile
from opportunity_match_pipeline import evaluate_row


def _evaluate(row: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    result = evaluate_row(row, profile=profile)
    return {
        "external_id": row["external_id"],
        "score": int(result["profile_score"]),
        "reason": result["reason"],
        "decision": result["decision"],
    }


def _rank_unique(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank unique-score controlled candidates only; ties are a separate policy lane."""
    scores = [item["score"] for item in items]
    if len(scores) != len(set(scores)):
        raise ValueError("TIE_REQUIRES_SEPARATE_AUTHORITY_AUDIT")
    return sorted(items, key=lambda item: -item["score"])


def controlled_candidate_set() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    profile = base_profile()
    rows = []
    subject = base_opportunity()
    subject["external_id"] = "subject"
    rows.append(subject)

    high = copy.deepcopy(subject)
    high["external_id"] = "control-high"
    high["procedure_type"] = "open procedure"
    high["value_numeric"] = 120000
    high["value"] = "120000"
    rows.append(high)

    low = copy.deepcopy(subject)
    low["external_id"] = "control-low"
    low["country"] = "ESP"
    rows.append(low)

    evaluated = [_evaluate(row, profile) for row in rows]
    # If current rules saturate two items, lower the control deterministically;
    # the audit is about movement caused by subject semantics, not tie policy.
    if len({item["score"] for item in evaluated}) != len(evaluated):
        low["cpv"] = "79900000"
        evaluated = [_evaluate(row, profile) for row in (subject, high, low)]
    return evaluated, profile


def rank_counterfactual(feature: str, value: Any, k: int = 2) -> dict[str, Any]:
    before, profile = controlled_candidate_set()
    subject_row = base_opportunity()
    subject_row["external_id"] = "subject"
    after_subject = copy.deepcopy(subject_row)
    after_subject[feature] = value
    if feature == "value_numeric":
        after_subject["value"] = str(value)

    before_subject = next(item for item in before if item["external_id"] == "subject")
    after_eval = _evaluate(after_subject, profile)
    after = [after_eval if item["external_id"] == "subject" else item for item in before]
    before_ranked = _rank_unique(before)
    after_ranked = _rank_unique(after)
    old_rank = next(i for i, item in enumerate(before_ranked, 1) if item["external_id"] == "subject")
    new_rank = next(i for i, item in enumerate(after_ranked, 1) if item["external_id"] == "subject")
    before_top = {item["external_id"] for item in before_ranked[:k]}
    after_top = {item["external_id"] for item in after_ranked[:k]}
    if old_rank != new_rank and (("subject" in before_top) != ("subject" in after_top)):
        classification = "TOP_K_BOUNDARY_FLIP"
    elif old_rank != new_rank:
        classification = "EXPECTED_RANK_MOVE"
    else:
        classification = "NO_RANK_EFFECT"
    return {
        "feature": feature,
        "base_score": before_subject["score"],
        "new_score": after_eval["score"],
        "score_delta": after_eval["score"] - before_subject["score"],
        "old_rank": old_rank,
        "new_rank": new_rank,
        "top_k": k,
        "top_k_before": sorted(before_top),
        "top_k_after": sorted(after_top),
        "top_k_entry": "subject" not in before_top and "subject" in after_top,
        "top_k_exit": "subject" in before_top and "subject" not in after_top,
        "reason_changed": before_subject["reason"] != after_eval["reason"],
        "classification": classification,
    }


def run_rank_audit() -> dict[str, Any]:
    return {
        "status": "CONTROLLED_UNIQUE_SCORE_RANKING_ONLY",
        "cases": [
            rank_counterfactual("cpv", "79900000"),
            rank_counterfactual("country", "ESP"),
            rank_counterfactual("value_numeric", 6_000_000),
            rank_counterfactual("procedure_type", "restricted procedure"),
        ],
        "limitations": [
            "ties intentionally excluded pending tie-break authority audit",
            "Top-K movement is customer-impact evidence, not correctness proof",
            "synthetic candidate set is not market ranking quality",
        ],
    }
