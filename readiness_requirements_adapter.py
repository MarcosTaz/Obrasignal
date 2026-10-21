"""Optional adapter from Opportunity Requirements v0 into Readiness v0.

The dependency is deliberately soft: if Opportunity Requirements is absent,
unsupported, or cannot evaluate the available canonical opportunity fields, this
adapter returns ``None`` so Readiness preserves ELIGIBILITY as UNKNOWN.

No private Requirements storage is read here.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Fields explicitly supported by the public Opportunity Requirements v0
# structured extractor. Presence of none of these means we have no defensible
# requirements input contract.
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


def _assessment_to_readiness_item(assessment: Any) -> dict[str, Any]:
    requirement = assessment.requirement
    evidence = tuple(getattr(requirement, "evidence", ()) or ())
    primary = evidence[0] if evidence else None
    source_ref = getattr(primary, "source_ref", None)
    locator = getattr(primary, "locator", None)
    evidence_ref = f"{source_ref}#{locator}" if source_ref and locator else source_ref
    priority = str(getattr(requirement, "priority", "UNKNOWN") or "UNKNOWN").upper()
    mandatory = priority not in {"OPTIONAL", "PREFERRED"}
    eligibility = str(getattr(assessment, "eligibility", "UNKNOWN") or "UNKNOWN").upper()
    if getattr(assessment, "known_blocker", False):
        status = "NOT_MET"
    elif eligibility == "MET":
        status = "MET"
    elif eligibility == "NOT_MET":
        status = "NOT_MET"
    else:
        # NOT_EVALUATED is deliberately UNKNOWN to Readiness. Lack of company
        # evidence cannot be promoted to a blocker or a pass.
        status = "UNKNOWN"
    return {
        "code": getattr(requirement, "requirement_id", None),
        "name": getattr(requirement, "description", None) or getattr(requirement, "requirement_type", None) or "requirement",
        "mandatory": mandatory,
        "status": status,
        "source_ref": source_ref,
        "evidence_ref": evidence_ref,
    }


def _coverage_is_complete(checklist: Any, assessed: Any) -> bool:
    """Recognize only an explicit future completeness assertion.

    Opportunity Requirements v0 does not currently expose one, therefore its
    extracted checklist is useful evidence but cannot by itself prove that every
    mandatory procurement requirement has been discovered.
    """
    return (
        getattr(assessed, "coverage_complete", None) is True
        or getattr(checklist, "coverage_complete", None) is True
    )


def resolve_requirements(
    account_id: str,
    opportunity: Mapping[str, Any],
    company_state: Mapping[str, Any] | None,
) -> list[dict[str, Any]] | None:
    """Return Readiness-shaped requirement assessments when defensible.

    ``None`` means the Requirements capability/input is unavailable and causes
    Readiness to emit a critical UNKNOWN. Partial Requirements output is useful
    for surfaced blockers/verified facts but remains accompanied by a critical
    coverage UNKNOWN until the public contract explicitly attests completeness.
    """
    if not _has_explicit_requirement_input(opportunity):
        return None
    try:
        from opportunity_requirements import assess_checklist, build_checklist
        checklist = build_checklist(_source_context(opportunity), include_text_rules=False)
        assessed = assess_checklist(checklist, company_state, account_id=account_id)
        items = [_assessment_to_readiness_item(item) for item in assessed.assessments]
    except Exception:
        # Requirements is optional to this capability. Any contract/subsystem
        # failure must fail closed to UNKNOWN rather than break the opportunity
        # detail or fabricate readiness.
        return None

    if not _coverage_is_complete(checklist, assessed):
        source = str(opportunity.get("source") or "").strip()
        external_id = str(opportunity.get("external_id") or opportunity.get("id") or "").strip()
        source_ref = f"{source}:{external_id}" if source and external_id else source or external_id or None
        items.append({
            "code": "requirements_coverage_unverified",
            "name": "Complete mandatory-requirements coverage has not been verified.",
            "mandatory": True,
            "status": "UNKNOWN",
            "source_ref": source_ref,
            "evidence_ref": None,
        })
    return items
