"""Single explicit adapter from the legacy Company Profile into Company State v1."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
import unicodedata
from typing import Any, Mapping

from company_state import (
    CompanyFact,
    CompanyState,
    FactCategory,
    KnowledgeState,
    Provenance,
    ProvenanceBasis,
)


def _slug(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:48] or "unknown"


def company_state_from_profile(profile: Mapping[str, Any] | None, *, account_id: str, as_of: datetime) -> CompanyState:
    """Project only defensible profile facts; absence never becomes a negative fact.

    Company Profile is primarily a commercial-preference contract. Services,
    capability tags and recorded certifications are explicit company declarations,
    but profile market geography must not be relabelled as proven operational
    geography. Countries/regions therefore become ``geography.preferred_*``
    facts. An explicitly supplied operational radius keeps its narrower meaning.
    Commercial min/max values are not imported as financial capacity because
    they are preferences and the legacy profile has no explicit currency/capital
    semantics.
    """
    data = dict(profile or {})
    stored_account = str(data.get("account_id") or account_id).strip()
    if stored_account != account_id:
        from company_state import TenantBoundaryError
        raise TenantBoundaryError("company profile belongs to a different account")

    declared = Provenance(ProvenanceBasis.DECLARED, source_ref="company_profile")
    profile_default = Provenance(ProvenanceBasis.PROFILE, source_ref="company_profile:legacy-default")
    facts: list[CompanyFact] = []

    seen_capabilities: set[str] = set()
    for source_field in ("services", "capability_tags"):
        for raw in data.get(source_field) or []:
            label = str(raw).strip()
            if not label:
                continue
            normalized = label.casefold()
            if normalized in seen_capabilities:
                continue
            seen_capabilities.add(normalized)
            facts.append(CompanyFact(
                category=FactCategory.CAPABILITY,
                code=f"capability.{_slug(label)}",
                knowledge=KnowledgeState.FACT,
                value={"label": label, "declared_via": source_field},
                provenance=declared,
            ))

    for raw in data.get("certifications") or []:
        label = str(raw).strip()
        if label:
            facts.append(CompanyFact(
                category=FactCategory.QUALIFICATION,
                code=f"qualification.{_slug(label)}",
                knowledge=KnowledgeState.FACT,
                value={"name": label, "status": "DECLARED_HELD", "validity": "UNKNOWN"},
                provenance=declared,
            ))

    countries = tuple(str(item).strip().upper() for item in (data.get("countries") or []) if str(item).strip())
    if countries:
        is_legacy_default = countries == ("PRT",) and not (data.get("regions") or []) and data.get("geographic_radius_km") is None
        facts.append(CompanyFact(
            category=FactCategory.GEOGRAPHY,
            code="geography.preferred_countries",
            knowledge=KnowledgeState.ASSUMPTION if is_legacy_default else KnowledgeState.FACT,
            value=list(countries),
            provenance=profile_default if is_legacy_default else declared,
        ))

    regions = [str(item).strip() for item in (data.get("regions") or []) if str(item).strip()]
    if regions:
        facts.append(CompanyFact(
            category=FactCategory.GEOGRAPHY,
            code="geography.preferred_regions",
            knowledge=KnowledgeState.FACT,
            value=regions,
            provenance=declared,
        ))

    radius = data.get("geographic_radius_km")
    if radius is not None and not isinstance(radius, bool):
        try:
            radius_decimal = Decimal(str(radius))
        except (InvalidOperation, ValueError, TypeError):
            radius_decimal = None
        if radius_decimal is not None and radius_decimal.is_finite() and radius_decimal >= 0:
            facts.append(CompanyFact(
                category=FactCategory.GEOGRAPHY,
                code="geography.practical_radius_km",
                knowledge=KnowledgeState.FACT,
                value=radius_decimal,
                unit="km",
                provenance=declared,
            ))

    unavailable = Provenance(ProvenanceBasis.UNAVAILABLE, source_ref="company_profile:not-modeled")
    present_codes = {fact.code for fact in facts}
    for category, code, unit in (
        (FactCategory.CAPACITY, "crew.total_count", "workers"),
        (FactCategory.AVAILABILITY, "crew.available_count", "workers"),
        (FactCategory.AVAILABILITY, "vehicle.available_count", "vehicles"),
        (FactCategory.GEOGRAPHY, "geography.base", None),
        (FactCategory.GEOGRAPHY, "geography.operating_countries", None),
    ):
        if code not in present_codes:
            facts.append(CompanyFact(
                category=category,
                code=code,
                knowledge=KnowledgeState.UNKNOWN,
                value=None,
                unit=unit,
                provenance=unavailable,
            ))

    return CompanyState(
        account_id=account_id,
        company_ref=None,
        as_of=as_of,
        facts=tuple(facts),
    )


def load_company_state_from_profile(*, account_id: str, as_of: datetime, profile_loader=None) -> CompanyState:
    """Repository-native profile loading seam; downstream code should use only this adapter."""
    if profile_loader is None:
        from company_profile import load_profile
        profile_loader = load_profile
    return company_state_from_profile(profile_loader(account_id), account_id=account_id, as_of=as_of)
