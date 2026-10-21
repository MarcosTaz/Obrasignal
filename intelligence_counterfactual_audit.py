"""Deterministic repository-safe scoring counterfactual audit.

This module measures current rule behaviour. It does not set product semantics,
weights, thresholds, probability, confidence, bid recommendation, or rollout.
"""
from __future__ import annotations

import copy
from typing import Any

from commercial_score_v2 import score_v2
from opportunity_match_pipeline import evaluate_row
from profile_scoring import personalized_score

COMMERCIAL_THRESHOLDS = (50, 65, 80)
PERSONALIZED_THRESHOLDS = (60, 75, 90)
LOT_THRESHOLDS = (50, 65, 80)
DECISION_THRESHOLDS = (60, 65, 75)
CAPS = {"NO_POSITIVE_EVIDENCE": 59, "HARD_BLOCKER": 35}


def base_profile() -> dict[str, Any]:
    return {
        "activity": "Climatização e instalações AVAC",
        "contract_interests": ["climatização", "AVAC"],
        "keywords": ["climatização", "AVAC"],
        "exclude_keywords": [],
        "countries": ["PRT"],
        "cpv_prefixes": ["4533"],
        "services": ["climatização", "AVAC"],
        "capability_tags": ["climatização", "AVAC"],
        "min_value": 50000,
        "max_value": 500000,
    }


def base_opportunity() -> dict[str, Any]:
    return {
        "source": "SYNTHETIC",
        "external_id": "counterfactual-base",
        "title": "Instalação de sistema de climatização AVAC",
        "description": "Empreitada de instalação e manutenção do sistema AVAC",
        "buyer": "Município",
        "country": "PRT",
        "cpv": "45331200",
        "value": "180000",
        "value_numeric": 180000,
        "deadline": "2099-12-31T12:00:00+00:00",
        "procedure_type": "open procedure",
        "locations": [{"country": "PRT", "city": "Leiria"}],
    }


def _threshold_crossings(before: int, after: int, thresholds: tuple[int, ...]) -> list[dict[str, Any]]:
    crossings = []
    for threshold in thresholds:
        before_in = before >= threshold
        after_in = after >= threshold
        if before_in != after_in:
            crossings.append({"threshold": threshold, "from": before_in, "to": after_in})
    return crossings


def _reason_delta(before: list[str] | str, after: list[str] | str) -> dict[str, list[str]]:
    before_set = set(before if isinstance(before, list) else [part.strip() for part in before.split(";") if part.strip()])
    after_set = set(after if isinstance(after, list) else [part.strip() for part in after.split(";") if part.strip()])
    return {"added": sorted(after_set - before_set), "removed": sorted(before_set - after_set)}


def _rank(values: dict[str, int]) -> list[str]:
    return [key for key, _ in sorted(values.items(), key=lambda item: (-item[1], item[0]))]


def _rank_delta(base_score: int, new_score: int) -> dict[str, Any]:
    peers = {"control-high": base_score + 3, "subject": base_score, "control-low": max(0, base_score - 3)}
    before = _rank(peers)
    peers["subject"] = new_score
    after = _rank(peers)
    return {
        "before": before.index("subject") + 1,
        "after": after.index("subject") + 1,
        "delta": (after.index("subject") + 1) - (before.index("subject") + 1),
    }


def commercial_counterfactual(feature: str, value: Any) -> dict[str, Any]:
    before_row = base_opportunity()
    after_row = copy.deepcopy(before_row)
    after_row[feature] = value
    if feature == "value":
        after_row["value_numeric"] = value
    before = score_v2(before_row)
    after = score_v2(after_row)
    return {
        "layer": "commercial",
        "feature": feature,
        "base_score": before["score"],
        "new_score": after["score"],
        "delta": after["score"] - before["score"],
        "component_delta": {
            key: after["components"].get(key, 0) - before["components"].get(key, 0)
            for key in sorted(set(before["components"]) | set(after["components"]))
        },
        "reason_delta": _reason_delta(before["reasons"], after["reasons"]),
        "threshold_crossed": _threshold_crossings(before["score"], after["score"], COMMERCIAL_THRESHOLDS),
        "rank_delta": _rank_delta(before["score"], after["score"]),
    }


def personalized_counterfactual(feature: str, value: Any) -> dict[str, Any]:
    row = base_opportunity()
    profile = base_profile()
    base_commercial = score_v2(row)["score"]
    before = personalized_score(row, base_score=base_commercial, profile=profile)
    after_row = copy.deepcopy(row)
    after_profile = copy.deepcopy(profile)
    if feature.startswith("profile."):
        after_profile[feature.split(".", 1)[1]] = value
    else:
        after_row[feature] = value
        if feature == "value":
            after_row["value_numeric"] = value
    after = personalized_score(after_row, base_score=base_commercial, profile=after_profile)
    return {
        "layer": "personalized",
        "feature": feature,
        "base_score": before[0],
        "new_score": after[0],
        "delta": after[0] - before[0],
        "reason_delta": _reason_delta(before[3], after[3]),
        "threshold_crossed": _threshold_crossings(before[0], after[0], PERSONALIZED_THRESHOLDS),
        "rank_delta": _rank_delta(before[0], after[0]),
    }


def pipeline_counterfactual(feature: str, value: Any) -> dict[str, Any]:
    before_row = base_opportunity()
    after_row = copy.deepcopy(before_row)
    profile = base_profile()
    if feature.startswith("profile."):
        after_profile = copy.deepcopy(profile)
        after_profile[feature.split(".", 1)[1]] = value
    else:
        after_profile = profile
        after_row[feature] = value
        if feature == "value":
            after_row["value_numeric"] = value
    before = evaluate_row(before_row, profile=profile)
    after = evaluate_row(after_row, profile=after_profile)
    return {
        "layer": "pipeline",
        "feature": feature,
        "base_score": before["profile_score"],
        "new_score": after["profile_score"],
        "delta": after["profile_score"] - before["profile_score"],
        "base_lot_score": before["lot_score"],
        "new_lot_score": after["lot_score"],
        "lot_delta": after["lot_score"] - before["lot_score"],
        "base_decision": before["decision"],
        "new_decision": after["decision"],
        "actionability_impact": before["decision"] != after["decision"] or bool(before["hard_capability_blockers"]) != bool(after["hard_capability_blockers"]),
        "hard_blockers_before": before["hard_capability_blockers"],
        "hard_blockers_after": after["hard_capability_blockers"],
        "reason_delta": _reason_delta(before["reason"], after["reason"]),
        "threshold_crossed": _threshold_crossings(before["profile_score"], after["profile_score"], DECISION_THRESHOLDS),
        "rank_delta": _rank_delta(before["profile_score"], after["profile_score"]),
    }


def run_feature_dominance_audit() -> dict[str, Any]:
    commercial = [
        commercial_counterfactual("cpv", "79900000"),
        commercial_counterfactual("description", "Serviço administrativo sem execução de obra"),
        commercial_counterfactual("deadline", "2000-01-01T12:00:00+00:00"),
        commercial_counterfactual("value", 6_000_000),
        commercial_counterfactual("procedure_type", "restricted procedure"),
    ]
    personalized = [
        personalized_counterfactual("title", "Aquisição de mobiliário de escritório"),
        personalized_counterfactual("country", "ESP"),
        personalized_counterfactual("cpv", "79900000"),
        personalized_counterfactual("value", 6_000_000),
        personalized_counterfactual("profile.keywords", ["pintura industrial"]),
    ]
    pipeline = [
        pipeline_counterfactual("deadline", "2000-01-01T12:00:00+00:00"),
        pipeline_counterfactual("value", 6_000_000),
        pipeline_counterfactual("country", "ESP"),
        pipeline_counterfactual("cpv", "79900000"),
        pipeline_counterfactual("profile.keywords", ["pintura industrial"]),
    ]
    return {
        "status": "SYNTHETIC_COUNTERFACTUAL_ONLY",
        "commercial": commercial,
        "personalized": personalized,
        "pipeline": pipeline,
        "thresholds": {
            "commercial": list(COMMERCIAL_THRESHOLDS),
            "personalized": list(PERSONALIZED_THRESHOLDS),
            "lot": list(LOT_THRESHOLDS),
            "decision": list(DECISION_THRESHOLDS),
            "caps": CAPS,
        },
        "limitations": [
            "one synthetic profile/opportunity family; not market feature importance",
            "configured weights are not treated as empirical importance",
            "rank deltas use a controlled three-item candidate set only",
            "score semantics remain governed by #478",
        ],
    }
