"""Repository-safe reason fidelity audit for decision intelligence.

This module observes current scoring/explanation behaviour. It does not alter
weights, thresholds, labels, UI semantics, ranking policy, or production state.
"""
from __future__ import annotations

import copy
from typing import Any

from commercial_score_v2 import score_v2
from intelligence_counterfactual_audit import base_opportunity, base_profile
from opportunity_match_pipeline import evaluate_row
from profile_scoring import personalized_score


def _reason_set(value: Any) -> set[str]:
    if isinstance(value, list):
        return {str(part).strip() for part in value if str(part).strip()}
    return {part.strip() for part in str(value or "").split(";") if part.strip()}


def _delta(before: set[str], after: set[str]) -> dict[str, list[str]]:
    return {"added": sorted(after - before), "removed": sorted(before - after)}


def commercial_reason_counterfactual(feature: str, value: Any) -> dict[str, Any]:
    before_row = base_opportunity()
    after_row = copy.deepcopy(before_row)
    after_row[feature] = value
    if feature == "value_numeric":
        after_row["value"] = str(value)
    before = score_v2(before_row)
    after = score_v2(after_row)
    before_reasons = _reason_set(before["reasons"])
    after_reasons = _reason_set(after["reasons"])
    changed = before["score"] != after["score"]
    reason_changed = before_reasons != after_reasons
    if changed and reason_changed:
        classification = "SCORE_CHANGED_REASON_CHANGED_FAITHFULLY"
    elif changed and not reason_changed:
        classification = "SCORE_CHANGED_REASON_STALE"
    elif not changed and reason_changed:
        classification = "REASON_CHANGED_WITHOUT_SCORE_CAUSE"
    else:
        classification = "NO_MATERIAL_CHANGE"
    return {
        "layer": "commercial",
        "feature": feature,
        "base_score": before["score"],
        "new_score": after["score"],
        "score_delta": after["score"] - before["score"],
        "reason_delta": _delta(before_reasons, after_reasons),
        "classification": classification,
    }


def personalized_reason_counterfactual(feature: str, value: Any) -> dict[str, Any]:
    row = base_opportunity()
    profile = base_profile()
    commercial = score_v2(row)["score"]
    before = personalized_score(row, base_score=commercial, profile=profile)
    after_row = copy.deepcopy(row)
    after_profile = copy.deepcopy(profile)
    if feature.startswith("profile."):
        after_profile[feature.split(".", 1)[1]] = value
    else:
        after_row[feature] = value
    after = personalized_score(after_row, base_score=commercial, profile=after_profile)
    before_reasons = _reason_set(before[3])
    after_reasons = _reason_set(after[3])
    changed = before[0] != after[0]
    reason_changed = before_reasons != after_reasons
    if changed and reason_changed:
        classification = "SCORE_CHANGED_REASON_CHANGED_FAITHFULLY"
    elif changed and not reason_changed:
        classification = "SCORE_CHANGED_REASON_STALE"
    elif not changed and reason_changed:
        classification = "REASON_CHANGED_WITHOUT_SCORE_CAUSE"
    else:
        classification = "NO_MATERIAL_CHANGE"
    return {
        "layer": "personalized",
        "feature": feature,
        "base_score": before[0],
        "new_score": after[0],
        "score_delta": after[0] - before[0],
        "reason_delta": _delta(before_reasons, after_reasons),
        "classification": classification,
    }


def explanation_provenance(evaluation: dict[str, Any]) -> list[dict[str, Any]]:
    commercial = evaluation.get("commercial") or {}
    components = commercial.get("components") or {}
    capability = evaluation.get("capability_evidence") or {}
    cpv = evaluation.get("cpv_evidence") or {}
    economics = evaluation.get("economic_fit") or {}
    geo = evaluation.get("geography") or {}
    factors = ((evaluation.get("explanation") or {}).get("factors") or [])
    by_key = {factor.get("key"): factor for factor in factors}

    rows = [
        {
            "reason_key": "profile",
            "source_feature": "profile-derived score",
            "rule": "personalized_score + pipeline caps",
            "contribution_state": "KNOWN" if evaluation.get("profile_score") is not None else "UNKNOWN",
            "score_effect": evaluation.get("profile_score"),
            "customer_reason": (by_key.get("profile") or {}).get("reason"),
            "support_state": "GENERIC_PLACEHOLDER",
        },
        {
            "reason_key": "lot",
            "source_feature": "commercial + geography",
            "rule": "match_lot",
            "contribution_state": "KNOWN" if evaluation.get("lot_score") is not None else "UNKNOWN",
            "score_effect": evaluation.get("lot_score"),
            "customer_reason": (by_key.get("lot") or {}).get("reason"),
            "support_state": "GENERIC_PLACEHOLDER",
        },
        {
            "reason_key": "cpv",
            "source_feature": "cpv",
            "rule": "_cpv_evidence / commercial_score_v2.cpv_fit",
            "contribution_state": cpv.get("status") or "UNKNOWN",
            "score_effect": components.get("cpv_fit"),
            "customer_reason": (by_key.get("cpv") or {}).get("reason"),
            "support_state": "SUPPORTED_REASON" if cpv.get("strength") in {"STRONG", "WEAK"} else "UNKNOWN",
        },
        {
            "reason_key": "capability",
            "source_feature": "title/description capability terms",
            "rule": "capability_matches_text / commercial_score_v2.capability_fit",
            "contribution_state": "MATCH" if capability.get("matched") else "UNKNOWN",
            "score_effect": components.get("capability_fit"),
            "customer_reason": (by_key.get("capability") or {}).get("reason"),
            "support_state": "SUPPORTED_REASON" if capability.get("matched") else "UNKNOWN",
        },
        {
            "reason_key": "geography",
            "source_feature": "location/profile geography",
            "rule": "geographic_fit",
            "contribution_state": "KNOWN" if geo.get("reason") else "UNKNOWN",
            "score_effect": geo.get("score"),
            "customer_reason": (by_key.get("geography") or {}).get("reason"),
            "support_state": "SUPPORTED_REASON" if geo.get("reason") else "UNKNOWN",
        },
        {
            "reason_key": "economic_fit",
            "source_feature": "value/economic profile",
            "rule": "evaluate_economic_fit",
            "contribution_state": economics.get("status") or "UNKNOWN",
            "score_effect": economics.get("score"),
            "customer_reason": (by_key.get("economic_fit") or {}).get("reason"),
            "support_state": "SUPPORTED_REASON" if economics.get("status") else "UNKNOWN",
        },
    ]
    return rows


def detect_unsupported_positive_explanations(evaluation: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    blockers = evaluation.get("hard_capability_blockers") or []
    for item in explanation_provenance(evaluation):
        text = str(item.get("customer_reason") or "").casefold()
        positive = any(token in text for token in ("compatibilidade", "compatível", "favorável", "favoravel"))
        if item["support_state"] == "GENERIC_PLACEHOLDER" and positive:
            findings.append({**item, "classification": "GENERIC_PLACEHOLDER"})
        elif positive and item["contribution_state"] in {"UNKNOWN", "NONE"}:
            findings.append({**item, "classification": "POSITIVE_REASON_WITHOUT_POSITIVE_SIGNAL"})
    if blockers:
        for finding in findings:
            if finding["reason_key"] in {"profile", "lot"}:
                finding["classification"] = "UNSUPPORTED_POSITIVE_CLAIM"
    return findings


def run_reason_fidelity_audit() -> dict[str, Any]:
    base = evaluate_row(base_opportunity(), profile=base_profile())
    blocked_row = base_opportunity()
    blocked_row["cpv"] = "79900000"
    blocked = evaluate_row(blocked_row, profile=base_profile())
    return {
        "status": "SYNTHETIC_REASON_FIDELITY_ONLY",
        "counterfactuals": [
            commercial_reason_counterfactual("cpv", "79900000"),
            commercial_reason_counterfactual("description", "Serviço administrativo sem execução de obra"),
            commercial_reason_counterfactual("deadline", "2000-01-01T12:00:00+00:00"),
            commercial_reason_counterfactual("value_numeric", 6_000_000),
            commercial_reason_counterfactual("procedure_type", "restricted procedure"),
            personalized_reason_counterfactual("profile.keywords", ["pintura industrial"]),
        ],
        "base_provenance": explanation_provenance(base),
        "blocked_findings": detect_unsupported_positive_explanations(blocked),
        "limitations": [
            "internal consistency only; not market relevance proof",
            "generic placeholders are classified, not autonomously rewritten",
            "score naming/semantic authority remains #478",
        ],
    }
