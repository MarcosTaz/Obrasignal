"""Company-specific scoring for ObraSignal."""
from __future__ import annotations

import re
from company_profile import load_profile, derive_profile


def _text(row):
    return re.sub(r"\s+", " ", " ".join(str(row.get(k) or "") for k in ("title", "description", "buyer")).lower())


def _value(row):
    raw = str(row.get("value") or "")
    nums = re.findall(r"\d+(?:[\.,]\d+)?", raw.replace(" ", ""))
    if not nums:
        return None
    token = nums[0]
    try:
        if "," in token and "." in token:
            token = token.replace(".", "").replace(",", ".")
        elif "," in token:
            token = token.replace(",", ".")
        return float(token)
    except ValueError:
        return None


def personalized_score(row, base_score=None):
    profile = load_profile()
    profile = derive_profile(profile.get("activity", ""), profile)
    base = int(row.get("score") if base_score is None else base_score or 0)
    score = base
    text = _text(row)
    hits, excludes = [], []

    for keyword in profile.get("keywords", []):
        k = str(keyword).lower().strip()
        if k and k in text:
            score += 6
            hits.append(k)
    for keyword in profile.get("exclude_keywords", []):
        k = str(keyword).lower().strip()
        if k and k in text:
            score -= 8
            excludes.append(k)

    countries = {str(x).upper() for x in profile.get("countries", []) if x}
    country = str(row.get("country") or "").upper()
    if countries and country:
        score += 8 if country in countries else -4

    prefixes = tuple(str(x) for x in profile.get("cpv_prefixes", []) if x)
    cpv = re.sub(r"\s+", "", str(row.get("cpv") or ""))
    if prefixes and any(part.startswith(prefixes) for part in cpv.split("|")):
        score += 8

    value = _value(row)
    if value is not None and profile.get("min_value") is not None:
        score += 5 if value >= float(profile["min_value"]) else -3
    if value is not None and profile.get("max_value") is not None and value > float(profile["max_value"]):
        score -= 5

    score = max(0, min(100, score))
    if score >= 90:
        label, cls = "ALERTA MÁXIMO", "hot"
    elif score >= 75:
        label, cls = "ALERTA", "hot"
    elif score >= 60:
        label, cls = "NO RADAR", "good"
    else:
        label, cls = "BAIXA PRIORIDADE", "low"

    reasons = []
    if hits:
        reasons.append("perfil: " + ", ".join(dict.fromkeys(hits[:4])))
    if countries and country in countries:
        reasons.append("mercado preferido")
    if prefixes and any(part.startswith(prefixes) for part in cpv.split("|")):
        reasons.append("CPV compatível")
    if excludes:
        reasons.append("penalizado: " + ", ".join(dict.fromkeys(excludes[:2])))
    return score, label, cls, "; ".join(reasons) if reasons else "correspondência pelo score comercial"
