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
        aliases = {
            "services": "service_types",
            "capabilities": "capability_tags",
            # Profiles written by the first web form used these names. Keep
            # accepting them at the matcher boundary so an old persisted JSON
            # document cannot silently lose its commercial envelope.
            "min_value": "minimum_value",
            "max_value": "maximum_value",
        }
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
    values = dict(profile or {})
    if not values.get("services") and values.get("contract_interests"):
        values["services"] = values["contract_interests"]
    capability = CapabilityProfile.from_dict(values)
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


_STOPWORDS = {
    "a", "as", "o", "os", "de", "da", "das", "do", "dos", "e", "em",
    "para", "por", "com", "sem", "uma", "um", "the", "and", "of", "for",
    "servico", "servicos", "service", "services", "trabalho", "trabalhos",
    "contrato", "contratos",
}


def _stem_token(token: str) -> str:
    """Small deterministic stemmer for the inflections common in PT tenders.

    This is intentionally not a general linguistic stemmer. It only normalizes
    forms that otherwise make a user's natural-language profile miss an obvious
    tender, e.g. ``instalações elétricas`` vs ``instalação elétrica``.
    """
    token = str(token or "")
    if len(token) > 6 and token.endswith("oes"):
        token = token[:-3]
    elif len(token) > 5 and token.endswith("ao"):
        token = token[:-2]
    if len(token) > 4 and token.endswith("s"):
        token = token[:-1]
    return token


def _semantic_tokens(value: str) -> list[str]:
    normalized = _normalize_term(value)
    tokens = []
    for raw in re.findall(r"[a-z0-9]+", normalized):
        if raw in _STOPWORDS or len(raw) < 4:
            continue
        stem = _stem_token(raw)
        if len(stem) >= 4 and stem not in tokens:
            tokens.append(stem)
    return tokens


def _semantic_term_match(text: str, term: str) -> bool:
    """Require all meaningful words from a profile phrase to occur in the tender.

    Exact phrase matching remains preferred, but word order and conservative
    singular/plural differences no longer make a saved company specification
    disappear from ranking evidence.
    """
    wanted = _semantic_tokens(term)
    if not wanted:
        return False
    available = set(_semantic_tokens(text))
    if len(wanted) == 1:
        # Single-word activity evidence is accepted only for a reasonably
        # specific token; short/generic words never become positive evidence.
        return len(wanted[0]) >= 5 and wanted[0] in available
    return all(token in available for token in wanted)


def _matches_label(text: str, label: str) -> bool:
    return _contains_term(text, label) or _semantic_term_match(text, label)


def capability_matches_text(profile: dict, text: str) -> dict:
    """Explain service/capability evidence found in an opportunity description.

    User-entered services, capability tags and the primary activity are all
    authoritative profile inputs. They are matched with conservative semantic
    normalization so natural Portuguese inflections do not silently erase a
    company's saved specifications from the Radar.
    """
    services = [str(item) for item in profile.get("services", []) if str(item).strip()]
    tags = [str(item) for item in profile.get("capability_tags", []) if str(item).strip()]
    activity = str(profile.get("activity") or "").strip()
    matched_services = [item for item in services if _matches_label(text, item)]
    matched_tags = [item for item in tags if _matches_label(text, item)]
    matched_activity = bool(activity and _matches_label(text, activity))
    evidence = matched_services + matched_tags + ([activity] if matched_activity else [])
    return {
        "status": "MATCH" if evidence else "UNKNOWN",
        "matched": bool(evidence),
        "matched_services": matched_services,
        "matched_capabilities": matched_tags,
        "matched_activity": activity if matched_activity else None,
        "evidence_count": len(evidence),
        "reason": (
            "foram encontradas capacidades da empresa na descrição"
            if evidence else
            "não foram encontradas capacidades explícitas na descrição"
        ),
    }
