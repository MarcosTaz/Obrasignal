"""Structured company capability model used by ObraSignal ranking.

This module is deliberately independent from the existing profile loader so the
new capability layer can be introduced without breaking current ingestion.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
import unicodedata


@dataclass
class CapabilityProfile:
    """What a company can do, where, and under which constraints."""

    name: str = ""
    activity: str = ""
    countries: list[str] = field(default_factory=lambda: ["PRT"])
    regions: list[str] = field(default_factory=list)
    geographic_radius_km: float | None = None
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


def _normalize_term(value: str) -> str:
    """Normalize Portuguese text enough for deterministic inflection matching."""
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _term_variants(value: str) -> set[str]:
    """Return conservative singular/plural variants for service labels."""
    term = _normalize_term(value)
    if not term:
        return set()
    variants = {term}
    words = term.split()
    last = words[-1]
    if len(last) > 3 and last.endswith("s"):
        variants.add(" ".join(words[:-1] + [last[:-1]]))
    elif len(last) > 3 and not last.endswith(("s", "x", "z")):
        variants.add(" ".join(words[:-1] + [last + "s"]))
    return variants


def _contains_term(text: str, term: str) -> bool:
    """Match a capability as a phrase rather than as an arbitrary substring."""
    normalized_text = _normalize_term(text)
    for variant in _term_variants(term):
        if re.search(rf"(?<!\w){re.escape(variant)}(?!\w)", normalized_text):
            return True
    return False


def capability_matches_text(profile: dict, text: str) -> dict:
    """Explain service/capability evidence found in an opportunity description."""
    services = [str(item) for item in profile.get("services", [])]
    tags = [str(item) for item in profile.get("capability_tags", [])]
    matched_services = [item for item in services if _contains_term(text, item)]
    matched_tags = [item for item in tags if _contains_term(text, item)]
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
