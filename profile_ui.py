from __future__ import annotations

from company_profile import save_profile

FIELD_ALIASES = {
    "countries": "countries",
    "regions": "regions",
    "radius": "geographic_radius_km",
    "services": "services",
    "capabilities": "capability_tags",
    "scales": "project_scales",
    "certifications": "certifications",
    "cpvs": "cpv_prefixes",
    "preferred": "preferred_procedure_types",
    "excluded": "excluded_procedure_types",
    "excluded_keywords": "exclude_keywords",
    "hard_exclusions": "hard_exclusions",
}
TEXT_FIELDS = {"name", "activity", "keywords"}
NUMERIC_FIELDS = {
    "radius": float,
    "min_value": float,
    "max_value": float,
    "economic_min_score": int,
    "min_deadline_days": int,
    "max_deadline_days": int,
}


def _split(value: str | None) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def profile_payload_from_form(form) -> dict:
    payload: dict = {}
    for key in TEXT_FIELDS:
        value = str(form.get(key, "")).strip()
        if value:
            payload[key] = value

    for form_key, profile_key in FIELD_ALIASES.items():
        values = _split(form.get(form_key))
        if values:
            payload[profile_key] = values

    for form_key, caster in NUMERIC_FIELDS.items():
        raw = str(form.get(form_key, "")).strip()
        if raw:
            payload[FIELD_ALIASES.get(form_key, form_key)] = caster(raw)

    return payload


def save_profile_from_form(form) -> dict:
    return save_profile(profile_payload_from_form(form))
