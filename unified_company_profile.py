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


def normalize_company_profile(profile: dict | None = None) -> dict:
    data = dict(profile or {})
    capability = build_capability_profile({**CAPABILITY_DEFAULTS, **data})
    normalized = dict(data)
    for key, value in capability.items():
        if key not in normalized or normalized[key] is None:
            normalized[key] = value
    return normalized
