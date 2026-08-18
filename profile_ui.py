from __future__ import annotations

from company_profile import save_profile

LIST_FIELDS = {
    "countries",
    "regions",
    "services",
    "capability_tags",
    "project_scales",
    "certifications",
    "cpv_prefixes",
    "preferred_procedure_types",
    "excluded_procedure_types",
    "exclude_keywords",
    "hard_exclusions",
}
NUMERIC_FIELDS = {
    "geographic_radius_km": float,
    "min_value": float,
    "max_value": float,
    "economic_min_score": int,
    "min_deadline_days": int,
    "max_deadline_days": int,
}
TEXT_FIELDS = {"name", "activity", "keywords"}


def _split(value: str | None) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def profile_payload_from_form(form) -> dict:
    payload: dict = {}
    for key in TEXT_FIELDS:
        value = str(form.get(key, "")).strip()
        if value:
            payload[key] = value
    for key in LIST_FIELDS:
        values = _split(form.get(key))
        if values:
            payload[key] = values
    for key, caster in NUMERIC_FIELDS.items():
        raw = str(form.get(key, "")).strip()
        if raw:
            payload[key] = caster(raw)
    return payload


def save_profile_from_form(form) -> dict:
    return save_profile(profile_payload_from_form(form))
