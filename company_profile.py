"""Company profile configuration for ObraSignal."""
from __future__ import annotations

import json
import os
import re

DEFAULT_PROFILE = {
    "name": "",
    "activity": "",
    "keywords": [],
    "countries": ["PRT"],
    "regions": [],
    "geographic_radius_km": None,
    "cpv_prefixes": ["45", "44", "42", "43"],
    "services": [],
    "capability_tags": [],
    "project_scales": [],
    "certifications": [],
    "profile_coordinates": None,
    "min_value": None,
    "max_value": None,
    "economic_min_score": 60,
    "min_deadline_days": None,
    "max_deadline_days": None,
    "preferred_procedure_types": [],
    "excluded_procedure_types": [],
    "exclude_keywords": [],
    "hard_exclusions": [],
}

LIST_FIELDS = {
    "keywords", "countries", "regions", "cpv_prefixes", "services",
    "capability_tags", "project_scales", "certifications",
    "preferred_procedure_types", "excluded_procedure_types",
    "exclude_keywords", "hard_exclusions",
}
NUMBER_FIELDS = {
    "min_value", "max_value", "economic_min_score", "min_deadline_days",
    "max_deadline_days", "geographic_radius_km",
}

ACTIVITY_RULES = [
    ("metalomecanica", ["metalomecânica", "metalomecanica", "estrutura metálica", "estruturas metálicas", "serralharia", "steel", "aço", "aco"], ["45", "42"]),
    ("construcao", ["construção", "construcao", "empreitada", "obras", "construction", "reabilitação", "reabilitacao"], ["45"]),
    ("coberturas", ["cobertura", "coberturas", "telhado", "roof", "fachada", "pavilhão", "pavilhao"], ["45", "44"]),
    ("armazens", ["armazém", "armazem", "warehouse", "pavilhão", "pavilhao", "industrial"], ["45", "44"]),
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _normalize_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, (list, tuple, set)):
        raise ValueError("list field must be a string or sequence")
    result = []
    for item in value:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _normalize_number(value, field):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if field == "economic_min_score" and not 0 <= number <= 100:
        raise ValueError("economic_min_score must be between 0 and 100")
    if field == "geographic_radius_km" and number < 0:
        raise ValueError("geographic_radius_km cannot be negative")
    if field.startswith("min_") or field.startswith("max_"):
        if number < 0:
            raise ValueError(f"{field} cannot be negative")
    return int(number) if number.is_integer() else number


def _normalize_coordinates(value):
    if value in (None, ""):
        return None
    if not isinstance(value, dict):
        raise ValueError("profile_coordinates must be an object")
    lat = float(value.get("lat"))
    lon = float(value.get("lon", value.get("long")))
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("profile_coordinates are outside valid ranges")
    return {"lat": lat, "lon": lon}


def normalize_profile(profile: dict | None = None) -> dict:
    incoming = profile or {}
    if not isinstance(incoming, dict):
        raise ValueError("profile must be an object")
    normalized = dict(DEFAULT_PROFILE)
    for key, value in incoming.items():
        if key not in DEFAULT_PROFILE:
            continue
        if key in LIST_FIELDS:
            normalized[key] = _normalize_list(value)
        elif key in NUMBER_FIELDS:
            normalized[key] = _normalize_number(value, key)
        elif key == "profile_coordinates":
            normalized[key] = _normalize_coordinates(value)
        else:
            normalized[key] = str(value).strip() if value is not None else ""

    if normalized["min_value"] is not None and normalized["max_value"] is not None and normalized["min_value"] > normalized["max_value"]:
        raise ValueError("min_value cannot exceed max_value")
    if normalized["min_deadline_days"] is not None and normalized["max_deadline_days"] is not None and normalized["min_deadline_days"] > normalized["max_deadline_days"]:
        raise ValueError("min_deadline_days cannot exceed max_deadline_days")
    return normalized


def derive_profile(activity: str, base: dict | None = None) -> dict:
    profile = normalize_profile(base)
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
        return normalize_profile(json.loads(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return dict(DEFAULT_PROFILE)


def save_profile(profile: dict) -> dict:
    path = os.getenv("OBRASIGNAL_PROFILE_FILE", "company_profile.json")
    normalized = derive_profile(str((profile or {}).get("activity") or ""), profile)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(normalized, fh, ensure_ascii=False, indent=2)
    return normalized
