"""Explainable economic fit for procurement opportunities.

ObraSignal does not predict profit. It scores whether an opportunity deserves
commercial/economic review using tender facts and rules defined by the company.
"""
from __future__ import annotations

from datetime import date, datetime

RULE_VERSION = "economic-fit-v2"


def _num(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm_set(values):
    return {str(v).strip().upper() for v in (values or []) if str(v).strip()}


def _days_to_deadline(deadline, today=None):
    if not deadline:
        return None
    try:
        if isinstance(deadline, datetime):
            target = deadline.date()
        elif isinstance(deadline, date):
            target = deadline
        else:
            target = datetime.fromisoformat(str(deadline).replace("Z", "+00:00")).date()
        base = today or date.today()
        return (target - base).days
    except (TypeError, ValueError):
        return None


def evaluate_economic_fit(value, profile=None, opportunity=None, today=None):
    """Score economic fit without claiming a profit estimate.

    Company rules are optional and fully explainable:
      min_value / max_value: preferred contract-value band
      min_deadline_days / max_deadline_days: preferred preparation window
      preferred_procedure_types / excluded_procedure_types
      economic_min_score: threshold for FAVOURABLE (default 60)

    Unknown data is never silently treated as a pass.
    """
    profile = profile or {}
    opportunity = opportunity or {}
    amount = _num(value)
    min_value = _num(profile.get("min_value"))
    max_value = _num(profile.get("max_value"))
    min_days = _num(profile.get("min_deadline_days"))
    max_days = _num(profile.get("max_deadline_days"))
    threshold = _num(profile.get("economic_min_score"))
    threshold = 60.0 if threshold is None else max(0.0, min(100.0, threshold))

    if amount is None or amount <= 0:
        return {
            "status": "UNKNOWN", "score": 0, "confidence": 0, "value": None,
            "rules": [], "reason": "valor do contrato inexistente ou inválido",
            "rule_version": RULE_VERSION,
        }

    rules = []
    score = 60.0
    company_rules = False

    def add_rule(name, passed, points_pass, points_fail, **details):
        nonlocal score, company_rules
        company_rules = True
        score += points_pass if passed else points_fail
        rules.append({"rule": name, "passed": passed, **details})

    if min_value is not None:
        add_rule("min_value", amount >= min_value, 20, -30, value=min_value)
    if max_value is not None:
        add_rule("max_value", amount <= max_value, 20, -20, value=max_value)

    deadline_days = _days_to_deadline(opportunity.get("deadline"), today=today)
    if min_days is not None:
        add_rule("min_deadline_days", deadline_days is not None and deadline_days >= min_days,
                 10, -15, value=min_days, observed=deadline_days)
    if max_days is not None:
        add_rule("max_deadline_days", deadline_days is not None and deadline_days <= max_days,
                 10, -10, value=max_days, observed=deadline_days)

    procedure = str(opportunity.get("procedure_type") or "").strip().upper()
    preferred_procedures = _norm_set(profile.get("preferred_procedure_types"))
    excluded_procedures = _norm_set(profile.get("excluded_procedure_types"))
    if preferred_procedures:
        add_rule("preferred_procedure_type", procedure in preferred_procedures, 10, -10,
                 value=sorted(preferred_procedures), observed=procedure or None)
    if excluded_procedures:
        add_rule("excluded_procedure_type", not procedure or procedure not in excluded_procedures,
                 0, -40, value=sorted(excluded_procedures), observed=procedure or None)

    score = max(0.0, min(100.0, score))
    if not company_rules:
        status = "REVIEW"
        confidence = 25
        reason = "dados conhecidos, mas a empresa ainda não definiu regras económicas"
    elif score >= threshold:
        status = "FAVOURABLE"
        confidence = 80
        reason = "a oportunidade cumpre as regras económicas definidas pela empresa"
    else:
        status = "UNFAVOURABLE"
        confidence = 80
        reason = "a oportunidade não cumpre as regras económicas definidas pela empresa"

    return {
        "status": status,
        "score": round(score),
        "confidence": confidence,
        "value": round(amount, 2),
        "rules": rules,
        "reason": reason,
        "rule_version": RULE_VERSION,
    }
