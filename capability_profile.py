"""Structured company capability model used by ObraSignal ranking.

This module is deliberately independent from the existing profile loader so the
new capability layer can be introduced without breaking current ingestion.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CapabilityProfile:
    """What a company can do, where, and under which constraints."""

    name: str = ""
    activity: str = ""
    countries: list[str] = field(default_factory=lambda: ["PRT"])
    regions: list[str] = field(default_factory=list)
    geographic_radius_km: float | None = None
    profile_coordinates: list[dict] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    capability_tags: list[str] = field(default_factory=list)
    cpv_prefixes: list[str] = field(default_factory=list)
    project_scales: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    min_value: float | None = None
    max_value: float | None = None
    preferred_procedure_types: list[str] = field(default_factory=list)
    excluded_procedure_types: list[str] = field(default_factory=list)
    hard_exclusions: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict | None = None) -> "CapabilityProfile":
        data = data or {}
        aliases = {"services": "service_types", "capabilities": "capability_tags"}
        values = dict(data)
        for target, source in aliases.items():
            if target not in values and source in values:
                values[target] = values[source]
        fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{key: values[key] for key in fields if key in values})

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "activity": self.activity,
            "countries": list(self.countries),
            "regions": list(self.regions),
            "geographic_radius_km": self.geographic_radius_km,
            "profile_coordinates": [dict(point) for point in self.profile_coordinates],
            "services": list(self.services),
            "capability_tags": list(self.capability_tags),
            "cpv_prefixes": list(self.cpv_prefixes),
            "project_scales": list(self.project_scales),
            "certifications": list(self.certifications),
            "min_value": self.min_value,
            "max_value": self.max_value,
            "preferred_procedure_types": list(self.preferred_procedure_types),
            "excluded_procedure_types": list(self.excluded_procedure_types),
            "hard_exclusions": list(self.hard_exclusions),
        }


def build_capability_profile(profile: dict | None = None) -> dict:
    """Normalize an existing company profile into the capability contract."""
    capability = CapabilityProfile.from_dict(profile)
    return capability.to_dict()


def capability_matches_text(profile: dict, text: str) -> dict:
    """Explain service/capability evidence found in an opportunity description."""
    haystack = (text or "").casefold()
    services = [str(item) for item in profile.get("services", [])]
    tags = [str(item) for item in profile.get("capability_tags", [])]
    matched_services = [item for item in services if item.casefold() in haystack]
    matched_tags = [item for item in tags if item.casefold() in haystack]
    evidence = matched_services + matched_tags
    return {
        "matched": bool(evidence),
        "matched_services": matched_services,
        "matched_capabilities": matched_tags,
        "evidence_count": len(evidence),
        "reason": (
            "foram encontradas capacidades da empresa na descrição"
            if evidence else
            "não foram encontradas capacidades explícitas na descrição"
        ),
    }
