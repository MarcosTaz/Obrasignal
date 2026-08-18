"""Company profile configuration for ObraSignal.

The profile is intentionally human-readable: a company can describe what it
actually does, while the system derives matching keywords and CPV families.
"""
from __future__ import annotations

import json
import os
import re

DEFAULT_PROFILE = {
    "name": "",
    "activity": "",
    "keywords": [],
    "countries": ["PRT"],
    "cpv_prefixes": ["45", "44", "42", "43"],
    "min_value": None,
    "max_value": None,
    "exclude_keywords": [],
}

ACTIVITY_RULES = [
    ("metalomecanica", ["metalomecânica", "metalomecanica", "estrutura metálica", "estruturas metálicas", "serralharia", "steel", "aço", "aco"], ["45", "42"]),
    ("construcao", ["construção", "construcao", "empreitada", "obras", "construction", "reabilitação", "reabilitacao"], ["45"]),
    ("coberturas", ["cobertura", "coberturas", "telhado", "roof", "fachada", "pavilhão", "pavilhao"], ["45", "44"]),
    ("armazens", ["armazém", "armazem", "warehouse", "pavilhão", "pavilhao", "industrial"], ["45", "44"]),
]


def _normalize(text: str) -> str:
    text = (text or "").lower()
    return re.sub(r"\s+", " ", text).strip()


def derive_profile(activity: str, base: dict | None = None) -> dict:
    """Derive keywords/CPV families from a natural-language activity."""
    profile = dict(DEFAULT_PROFILE)
    if base:
        profile.update({k: v for k, v in base.items() if v is not None})
    activity_n = _normalize(activity)
    profile["activity"] = activity or profile.get("activity", "")
    keywords = list(profile.get("keywords") or [])
    cpvs = list(profile.get("cpv_prefixes") or [])
    for _, terms, prefixes in ACTIVITY_RULES:
        if any(term in activity_n for term in terms):
            for term in terms:
                if term not in keywords:
                    keywords.append(term)
            for prefix in prefixes:
                if prefix not in cpvs:
                    cpvs.append(prefix)
    profile["keywords"] = keywords
    profile["cpv_prefixes"] = cpvs
    return profile


def load_profile() -> dict:
    raw = os.getenv("OBRASIGNAL_PROFILE_JSON", "").strip()
    if not raw:
        return dict(DEFAULT_PROFILE)
    try:
        profile = dict(DEFAULT_PROFILE)
        profile.update(json.loads(raw))
        return profile
    except (TypeError, ValueError):
        return dict(DEFAULT_PROFILE)


def save_profile(profile: dict) -> dict:
    """Persist profile in a local JSON file and return normalized data."""
    path = os.getenv("OBRASIGNAL_PROFILE_FILE", "company_profile.json")
    normalized = dict(DEFAULT_PROFILE)
    normalized.update(profile or {})
    normalized = derive_profile(normalized.get("activity", ""), normalized)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(normalized, fh, ensure_ascii=False, indent=2)
    return normalized
