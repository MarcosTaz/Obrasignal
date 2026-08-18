from __future__ import annotations

from typing import Any


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

NUMERIC_RANGES = {
    "economic_min_score": (0, 100),
    "geographic_radius_km": (0, None),
    "min_value": (0, None),
    "max_value": (0, None),
    "min_deadline_days": (0, None),
    "max_deadline_days": (0, None),
}


def validate_company_profile(profile: dict[str, Any] | None) -> list[str]:
    """Return explicit, user-facing configuration errors without mutating input."""
    data = profile or {}
    errors: list[str] = []

    for key in LIST_FIELDS:
        value = data.get(key)
        if value is not None and not isinstance(value, list):
            errors.append(f"{key}: deve ser uma lista.")
        elif isinstance(value, list) and any(not isinstance(item, str) or not item.strip() for item in value):
            errors.append(f"{key}: contém valores vazios ou inválidos.")

    for key, (minimum, maximum) in NUMERIC_RANGES.items():
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{key}: deve ser numérico.")
            continue
        if minimum is not None and value < minimum:
            errors.append(f"{key}: não pode ser inferior a {minimum}.")
        if maximum is not None and value > maximum:
            errors.append(f"{key}: não pode ser superior a {maximum}.")

    min_value = data.get("min_value")
    max_value = data.get("max_value")
    if min_value is not None and max_value is not None and min_value > max_value:
        errors.append("min_value: não pode ser superior a max_value.")

    min_deadline = data.get("min_deadline_days")
    max_deadline = data.get("max_deadline_days")
    if min_deadline is not None and max_deadline is not None and min_deadline > max_deadline:
        errors.append("min_deadline_days: não pode ser superior a max_deadline_days.")

    countries = data.get("countries") or []
    for country in countries:
        if len(country.strip()) != 3:
            errors.append(f"countries: código inválido '{country}'. Use ISO-3.")

    for cpv in data.get("cpv_prefixes") or []:
        value = cpv.strip()
        if not value.isdigit() or not (2 <= len(value) <= 8):
            errors.append(f"cpv_prefixes: prefixo inválido '{cpv}'.")

    return errors
