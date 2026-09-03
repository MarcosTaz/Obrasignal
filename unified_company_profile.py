"""Unified company profile normalization for ObraSignal.

Keeps the legacy company profile contract while embedding structured capability
fields so the UI, API and matching pipeline share one persisted source of truth.
"""
from __future__ import annotations

from capability_profile import build_capability_profile


CAPABILITY_DEFAULTS = {
    "regions": [],
    "geographic_radius_km": None,
    "services": [],
    "capability_tags": [],
    "project_scales": [],
    "certifications": [],
    "hard_exclusions": [],
}

_COUNTRY_ALIASES = {
    "CL": "CHL",
    "CHL": "CHL",
}


def _canonical_countries(values) -> list[str]:
    normalized = []
    for value in values or []:
        code = str(value or "").strip().upper()
        if not code:
            continue
        code = _COUNTRY_ALIASES.get(code, code)
        if code not in normalized:
            normalized.append(code)
    return normalized


def normalize_company_profile(profile: dict | None = None) -> dict:
    data = dict(profile or {})
    if "countries" in data:
        data["countries"] = _canonical_countries(data.get("countries"))
    capability = build_capability_profile({**CAPABILITY_DEFAULTS, **data})
    normalized = dict(data)
    for key, value in capability.items():
        if key not in normalized or normalized[key] is None:
            normalized[key] = value
    return normalized
