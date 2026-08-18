"""Company-specific scoring for ObraSignal.

The base commercial score remains the source-independent signal.  This module
adds a configurable profile layer so the same tender can rank differently for
different companies without changing the underlying notice data.

Configuration is supplied through OBRASIGNAL_PROFILE_JSON.  Example:
{
  "keywords": ["metalomecânica", "estrutura metálica", "serralharia"],
  "countries": ["PRT", "ESP", "FRA"],
  "cpv_prefixes": ["45", "44"],
  "min_value": 100000,
  "max_value": 2000000,
  "exclude_keywords": ["arquitetura", "fiscalização"]
}
"""
from __future__ import annotations

import json
import os
import re

DEFAULT_PROFILE = {
    "keywords": [
        "metalomecânica", "metalomecanica", "estrutura metálica",
        "estruturas metálicas", "estrutura metalica", "serralharia",
        "steel", "aço", "aco", "metal", "pavilhão", "pavilhao",
        "armazém", "armazem", "warehouse", "cobertura", "fachada",
        "montagem", "empreitada", "construção", "construcao", "construction",
    ],
    "countries": ["PRT"],
    "cpv_prefixes": ["45", "44", "42", "43"],
    "min_value": None,
    "max_value": None,
    "exclude_keywords": ["arquitetura", "arquitectura", "architecture", "fiscalização", "fiscalizacao", "consultoria", "consulting"],
}


def _load_profile():
    raw = os.getenv("OBRASIGNAL_PROFILE_JSON", "").strip()
    if not raw:
        return dict(DEFAULT_PROFILE)
    try:
        data = json.loads(raw)
        profile = dict(DEFAULT_PROFILE)
        profile.update({k: v for k, v in data.items() if v is not None})
        return profile
    except (TypeError, ValueError):
        return dict(DEFAULT_PROFILE)


def _text(row):
    return re.sub(r"\s+", " ", " ".join(str(row.get(k) or "") for k in ("title", "description", "buyer")).lower())


def _value(row):
    raw = str(row.get("value") or "")
    nums = re.findall(r"\d+(?:[\.,]\d+)?", raw.replace(" ", ""))
    if not nums:
        return None
    try:
        # Procurement values are commonly rendered as 1.234.567,89.
        token = nums[0]
        if "," in token and "." in token:
            token = token.replace(".", "").replace(",", ".")
        elif "," in token:
            token = token.replace(",", ".")
        return float(token)
    except ValueError:
        return None


def personalized_score(row, base_score=None):
    """Return (score, reason) for the active company profile.

    The profile score is deliberately bounded and additive: it cannot turn a
    completely irrelevant notice into a top match merely because of value.
    """
    profile = _load_profile()
    base = int(row.get("score") if base_score is None else base_score or 0)
    score = base
    text = _text(row)
    hits = []
    excludes = []

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
    if countries:
        if country in countries:
            score += 8
        elif country:
            score -= 4

    prefixes = tuple(str(x) for x in profile.get("cpv_prefixes", []) if x)
    cpv = re.sub(r"\s+", "", str(row.get("cpv") or ""))
    if prefixes and any(part.startswith(prefixes) for part in cpv.split("|")):
        score += 8

    value = _value(row)
    min_value = profile.get("min_value")
    max_value = profile.get("max_value")
    if value is not None and min_value is not None:
        score += 5 if value >= float(min_value) else -3
    if value is not None and max_value is not None and value > float(max_value):
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
