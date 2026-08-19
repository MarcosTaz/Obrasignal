"""Company-specific scoring for ObraSignal."""
from __future__ import annotations

import re
from company_profile import load_profile, derive_profile

_COUNTRY_ALIASES = {
    "PT": "PRT", "PRT": "PRT",
    "ES": "ESP", "ESP": "ESP",
    "FR": "FRA", "FRA": "FRA",
    "DE": "DEU", "DEU": "DEU",
}


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


def _country_code(value):
    return _COUNTRY_ALIASES.get(str(value or "").upper(), str(value or "").upper())


def personalized_score(row, base_score=None, profile=None):
    """Score a tender against one explicit company profile.

    `profile` is deliberately injectable so multi-account sync never falls back
    to the shared/default profile. The old call shape remains supported.
    """
    if profile is None:
        profile = derive_profile(load_profile().get("activity", ""), load_profile())
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
            score -= 12
            excludes.append(k)

    countries = {_country_code(x) for x in profile.get("countries", []) if x}
    country = _country_code(row.get("country"))
    preferred_country = bool(countries and country and country in countries)
    if countries and country:
        score += 10 if preferred_country else -4

    prefixes = tuple(str(x) for x in profile.get("cpv_prefixes", []) if x)
    cpv = re.sub(r"\s+", "", str(row.get("cpv") or ""))
    cpv_match = bool(prefixes and any(part.startswith(prefixes) for part in cpv.split("|")))
    if cpv_match:
        score += 10

    value = _value(row)
    value_in_range = False
    if value is not None and profile.get("min_value") is not None:
        if value >= float(profile["min_value"]):
            score += 5
            value_in_range = True
        else:
            score -= 3
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
    if preferred_country:
        reasons.append("mercado preferido")
    if cpv_match:
        reasons.append("CPV compatível")
    if value_in_range:
        reasons.append("valor dentro do intervalo")
    if excludes:
        reasons.append("penalizado: " + ", ".join(dict.fromkeys(excludes[:2])))
    return score, label, cls, "; ".join(reasons) if reasons else "correspondência pelo score comercial"
