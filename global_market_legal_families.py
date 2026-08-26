"""Source-family legal evidence and semantic change watch.

A family-level legal GREEN is scoped to the exact official source and licensed
content. It must never be used as proof of full national procurement coverage,
privacy compliance for arbitrary downstream data, Integration, or Golden.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import Literal

from market_scope_registry import SHARED_FAMILIES

LegalState = Literal[
    "LEGAL_GREEN",
    "LEGAL_AMBER",
    "LEGAL_RED",
    "LEGAL_UNKNOWN",
    "HUMAN_LEGAL_REVIEW_REQUIRED",
]
ChangeState = Literal["UNCHANGED", "MATERIAL_CHANGE", "UNKNOWN"]


@dataclass(frozen=True)
class SourceFamilyLegalEvidence:
    family: str
    authority: str
    source_name: str
    official_domain: str
    terms_url: str
    license_url: str
    open_data_policy_url: str
    license_type: str
    commercial_reuse: str
    redistribution: str
    attribution: str
    derivative_use: str
    database_rights: str
    api_terms: str
    robots_relevance: str
    personal_data_presence: str
    credential_requirements: str
    evidence_date: str
    evidence_fingerprint: str
    last_verified: str
    next_review: str
    classification: LegalState
    scope_limit: str
    countries: tuple[str, ...]


def _semantic_fingerprint(*material_claims: str) -> str:
    """Fingerprint the captured legal interpretation, not the remote page bytes."""
    normalized = "\n".join(claim.strip() for claim in material_claims)
    return "sha256:" + sha256(normalized.encode("utf-8")).hexdigest()


TED_EFORMS_LEGAL = SourceFamilyLegalEvidence(
    family="TED/eForms",
    authority="Publications Office of the European Union",
    source_name="Tenders Electronic Daily (TED) published procurement notices / Search API",
    official_domain="ted.europa.eu",
    terms_url="https://ted.europa.eu/en/legal-notice",
    license_url="https://ted.europa.eu/en/legal-notice",
    open_data_policy_url="https://docs.ted.europa.eu/ODS/latest/index.html",
    license_type="European Commission reuse policy; TED editorial content CC BY 4.0; SIMAP metadata CC0 1.0",
    commercial_reuse="PROVEN: published procurement notices may be freely reused commercially or non-commercially unless otherwise noted",
    redistribution="PROVEN within the legal-notice scope and subject to third-party-rights exceptions",
    attribution="Editorial SIMAP content requires CC BY 4.0 attribution; preserve TED/EU provenance for notice data",
    derivative_use="PROVEN for licensed/reusable content; mark changes where CC BY 4.0 applies",
    database_rights="No broader private database right is inferred beyond the official reuse notice and CC0 metadata dedication",
    api_terms="Search API provides anonymous published-notice access for analysis/reuse and explicitly lists commercial organisations as users",
    robots_relevance="Use official Search API/direct/bulk downloads; website scraping is unnecessary for the selected architecture",
    personal_data_presence="POSSIBLE: legal notice has separate personal-data rules; source reuse does not erase privacy obligations",
    credential_requirements="No authentication for TED Search API access to published notices",
    evidence_date="2026-08-26",
    evidence_fingerprint=_semantic_fingerprint(
        "published procurement notices can be freely reused for commercial or non-commercial purposes unless otherwise noted",
        "SIMAP editorial content CC BY 4.0",
        "SIMAP metadata CC0 1.0",
        "Search API anonymous for published notices and targeted to reusers including commercial organisations",
        "third-party works/private individuals may require additional rights handling",
    ),
    last_verified="2026-08-26",
    next_review="2026-09-26",
    classification="LEGAL_GREEN",
    scope_limit="GREEN only for TED-published procurement notice data/content within the official reuse notice; it does not prove below-threshold/national coverage or downstream privacy compliance.",
    countries=tuple(SHARED_FAMILIES["TED_EFORMS"]),
)


FAMILY_LEGAL_EVIDENCE = MappingProxyType({
    TED_EFORMS_LEGAL.family: TED_EFORMS_LEGAL,
})


COUNTRY_FAMILY_LEGAL_STATE = MappingProxyType({
    country: TED_EFORMS_LEGAL.classification
    for country in TED_EFORMS_LEGAL.countries
})


def compare_legal_fingerprint(
    previous_fingerprint: str | None,
    current_fingerprint: str | None,
) -> ChangeState:
    """Fail closed when either side is unavailable; never infer unchanged."""
    if not previous_fingerprint or not current_fingerprint:
        return "UNKNOWN"
    if previous_fingerprint != current_fingerprint:
        return "MATERIAL_CHANGE"
    return "UNCHANGED"


def revalidation_required(
    previous_classification: LegalState,
    previous_fingerprint: str | None,
    current_fingerprint: str | None,
) -> bool:
    """Any changed/unknown legal fingerprint invalidates inherited GREEN."""
    if previous_classification != "LEGAL_GREEN":
        return False
    return compare_legal_fingerprint(previous_fingerprint, current_fingerprint) != "UNCHANGED"


def validate_family_legal_registry() -> None:
    if TED_EFORMS_LEGAL.classification != "LEGAL_GREEN":
        raise RuntimeError("TED source-family legal evidence unexpectedly lost GREEN")
    if len(TED_EFORMS_LEGAL.countries) != 23:
        raise RuntimeError("TED legal family must match the 23 strategic SHARED markets")
    if set(TED_EFORMS_LEGAL.countries) != set(SHARED_FAMILIES["TED_EFORMS"]):
        raise RuntimeError("TED legal-family country mapping drifted")
    if not TED_EFORMS_LEGAL.evidence_fingerprint.startswith("sha256:"):
        raise RuntimeError("TED legal evidence fingerprint missing")


validate_family_legal_registry()
