"""Economic fit for procurement opportunities.

ObraSignal does not attempt to predict a company's profit. A company knows its
own labour, materials, subcontracting, financing and capacity costs better
than an external scoring engine can. This module therefore scores whether an
opportunity deserves economic review, using objective tender data and optional
company-defined rules.
"""
from __future__ import annotations

RULE_VERSION = "economic-fit-v1"


def _num(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm_set(values):
    return {str(v).strip().upper() for v in (values or []) if str(v).strip()}


def evaluate_economic_fit(value, profile=None):
    """Return an economic-fit score, never a claimed profit estimate.

    Supported company rules:
      min_value / max_value: preferred contract-value band
      economic_min_score: minimum fit score (default 60)
      economic_penalties: optional mapping for review rules

    The result explains which company rules were satisfied or violated. If no
    company-specific economic rules exist, the score is based only on whether
    contract value is known and remains explicitly low-confidence.
    """
    profile = profile or {}
    amount = _num(value)
    min_value = _num(profile.get("min_value"))
    max_value = _num(profile.get("max_value"))
    threshold = _num(profile.get("economic_min_score"))
    threshold = 60.0 if threshold is None else max(0.0, min(100.0, threshold))

    if amount is None or amount <= 0:
        return {
            "status": "UNKNOWN",
            "score": 0,
            "confidence": 0,
            "value": None,
            "rules": [],
            "reason": "valor do contrato inexistente ou inválido",
            "rule_version": RULE_VERSION,
        }

    rules = []
    score = 60.0
    company_rules = False

    if min_value is not None:
        company_rules = True
        if amount >= min_value:
            score += 20
            rules.append({"rule": "min_value", "passed": True, "value": min_value})
        else:
            score -= 30
            rules.append({"rule": "min_value", "passed": False, "value": min_value})

    if max_value is not None:
        company_rules = True
        if amount <= max_value:
            score += 20
            rules.append({"rule": "max_value", "passed": True, "value": max_value})
        else:
            score -= 20
            rules.append({"rule": "max_value", "passed": False, "value": max_value})

    score = max(0.0, min(100.0, score))
    if not company_rules:
        status = "REVIEW"
        confidence = 25
        reason = "valor conhecido, mas a empresa ainda não definiu regras económicas"
    elif score >= threshold:
        status = "FAVOURABLE"
        confidence = 80
        reason = "o valor do contrato está dentro das regras económicas definidas pela empresa"
    else:
        status = "UNFAVOURABLE"
        confidence = 80
        reason = "o valor do contrato não cumpre as regras económicas definidas pela empresa"

    return {
        "status": status,
        "score": round(score),
        "confidence": confidence,
        "value": round(amount, 2),
        "rules": rules,
        "reason": reason,
        "rule_version": RULE_VERSION,
    }
