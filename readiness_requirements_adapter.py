"""Public Opportunity Requirements -> Company State -> Readiness adapter.

The dependency remains soft: missing Requirements input or subsystem failure becomes
UNKNOWN. Tenant mismatches fail closed and are never converted to an empty company.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from company_state import CompanyState, TenantBoundaryError
from requirements_company_state_adapter import compare_checklist

STRUCTURED_REQUIREMENT_FIELDS = (
    "requirements",
    "minimum_turnover",
    "required_certifications",
    "minimum_experience_years",
    "insurance_requirements",
    "guarantee_requirements",
    "workforce_requirements",
    "equipment_requirements",
    "registration_requirements",
    "document_requirements",
    "geographical_requirements",
    "consortium_conditions",
)


def _has_explicit_requirement_input(opportunity: Mapping[str, Any]) -> bool:
    return any(field in opportunity for field in STRUCTURED_REQUIREMENT_FIELDS)


def _source_context(opportunity: Mapping[str, Any]) -> dict[str, Any]:
    source = str(opportunity.get("source") or "").strip()
    external_id = str(opportunity.get("external_id") or opportunity.get("id") or "").strip()
    context: dict[str, Any] = {
        "opportunity_id": external_id,
        "external_id": external_id,
        "source": source,
        "source_ref": f"{source}:{external_id}" if source and external_id else source or external_id,
        "source_version": opportunity.get("lifecycle_source_updated_at") or opportunity.get("source_updated_at"),
        "country": opportunity.get("country"),
        "jurisdiction": opportunity.get("jurisdiction") or opportunity.get("country"),
        "currency": opportunity.get("currency"),
    }
    for field in STRUCTURED_REQUIREMENT_FIELDS:
        if field in opportunity:
            context[field] = opportunity.get(field)
    return context


def _coverage_is_complete(checklist: Any) -> bool:
    """Recognize only an explicit public completeness assertion."""
    return getattr(checklist, "coverage_complete", None) is True


def resolve_requirements(
    account_id: str,
    opportunity: Mapping[str, Any],
    company_state: CompanyState | None,
) -> list[dict[str, Any]] | None:
    """Resolve structured requirements against canonical Company State.

    ``None`` means Requirements/input is unavailable. Partial extraction always
    retains a critical coverage UNKNOWN until Requirements publicly attests that
    all mandatory obligations have been discovered.
    """
    if not _has_explicit_requirement_input(opportunity):
        return None
    if company_state is not None and company_state.account_id != str(account_id or "").strip():
        raise TenantBoundaryError("company state belongs to a different account")

    try:
        from opportunity_requirements import build_checklist
        checklist = build_checklist(_source_context(opportunity), include_text_rules=False)
        comparisons = compare_checklist(checklist, company_state, account_id=account_id)
        items = [
            comparison.to_readiness_dict(requirement)
            for comparison, requirement in zip(comparisons, checklist.requirements)
        ]
    except TenantBoundaryError:
        raise
    except Exception:
        return None

    if not _coverage_is_complete(checklist):
        source = str(opportunity.get("source") or "").strip()
        external_id = str(opportunity.get("external_id") or opportunity.get("id") or "").strip()
        source_ref = f"{source}:{external_id}" if source and external_id else source or external_id or None
        items.append({
            "code": "requirements_coverage_unverified",
            "name": "Complete mandatory-requirements coverage has not been verified.",
            "mandatory": True,
            "status": "UNKNOWN",
            "reason": "Requirements v0 does not attest complete mandatory-document coverage.",
            "source_ref": source_ref,
            "evidence_ref": None,
            "evidence_refs": [],
            "company_fact_ids": [],
            "company_provenance_bases": [],
            "company_state_fingerprint": company_state.fingerprint if company_state is not None else None,
        })
    return items
