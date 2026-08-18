"""Company profile configuration for ObraSignal."""
from __future__ import annotations

import json
import os
import re

from company_profile_validation import validate_company_profile
from unified_company_profile import normalize_company_profile

DEFAULT_PROFILE = {
    "name": "",
    "activity": "",
    "keywords": [],
    "countries": ["PRT"],
    "cpv_prefixes": ["45", "44", "42", "43"],
    "min_value": None,
    "max_value": None,
    "economic_min_score": 60,
    "min_deadline_days": None,
    "max_deadline_days": None,
    "preferred_procedure_types": [],
    "excluded_procedure_types": [],
    "exclude_keywords": [],
    "regions": [],
    "geographic_radius_km": None,
    "services": [],
    "capability_tags": [],
    "project_scales": [],
    "certifications": [],
    "hard_exclusions": [],
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
    return normalize_company_profile(profile)


def _profile_path() -> str:
    return (
        os.getenv("OBRASIGNAL_PROFILE")
        or os.getenv("OBRASIGNAL_PROFILE_FILE")
        or "company_profile.json"
    )


def load_profile() -> dict:
    path = _profile_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        profile = dict(DEFAULT_PROFILE)
        profile.update(raw or {})
        return derive_profile(profile.get("activity", ""), profile)
    except (FileNotFoundError, OSError, TypeError, ValueError):
        raw = os.getenv("OBRASIGNAL_PROFILE_JSON", "").strip()
        if raw:
            try:
                profile = dict(DEFAULT_PROFILE)
                profile.update(json.loads(raw))
                return derive_profile(profile.get("activity", ""), profile)
            except (TypeError, ValueError):
                pass
        return dict(DEFAULT_PROFILE)


def save_profile(profile: dict) -> dict:
    path = _profile_path()
    normalized = dict(DEFAULT_PROFILE)
    normalized.update(profile or {})
    normalized = derive_profile(normalized.get("activity", ""), normalized)
    errors = validate_company_profile(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(normalized, fh, ensure_ascii=False, indent=2)
    return normalized
