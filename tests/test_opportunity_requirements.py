from decimal import Decimal

import pytest

from opportunity_requirements import (
    ConservativeTextRequirementExtractor,
    OpportunityRequirement,
    OpportunityRequirementsChecklist,
    RequirementEvidence,
    StructuredRequirementExtractor,
    assess_checklist,
    build_checklist,
    consolidate_requirements,
    normalize_currency,
    normalize_number,
    supersede,
)


def _ctx(**extra):
    base = {
        "opportunity_id": "opp-1",
        "source": "OFFICIAL",
        "source_version": "v1",
        "country": "PRT",
    }
    base.update(extra)
    return base


def _req(**overrides):
    data = dict(
        requirement_id="req-x",
        opportunity_id="opp-1",
        category="FINANCIAL",
        requirement_type="minimum_turnover",
        description="Minimum annual turnover EUR 2,000,000",
        priority="MANDATORY",
        operator=">=",
        required_value=2000000,
        unit=None,
        currency="EUR",
        period="annual",
        evidence=(RequirementEvidence("OFFICIAL", "field:minimum_turnover", raw_value="€2m"),),
        confidence="HIGH",
    )
    data.update(overrides)
    return OpportunityRequirement(**data)


def test_structured_financial_requirement_preserves_raw_and_normalized_semantics():
    req = StructuredRequirementExtractor().extract(_ctx(
        currency="EUR",
        minimum_turnover={
            "value": "€2m",
            "description": "Minimum annual turnover: €2m",
            "period": "average last 3 fiscal years",
        },
    ))[0]
    assert req.category == "FINANCIAL"
    assert req.requirement_type == "minimum_turnover"
    assert req.operator == ">="
    assert req.required_value == 2_000_000
    assert req.currency == "EUR"
    assert req.period == "average last 3 fiscal years"
    assert req.priority == "MANDATORY"
    assert req.evidence[0].raw_value == "€2m"
    assert req.evidence[0].locator == "field:minimum_turnover"
    assert req.confidence == "HIGH"


def test_currency_and_number_normalization_are_deterministic():
    assert normalize_currency("€") == "EUR"
    assert normalize_currency("GBP") == "GBP"
    assert normalize_number("2 million") == Decimal("2000000")
    assert normalize_number("2.000.000") == Decimal("2000000")
    assert normalize_number("1,25") == Decimal("1.25")


@pytest.mark.parametrize(
    "field_name,category,req_type",
    [
        ("required_certifications", "CERTIFICATION", "certification"),
        ("minimum_experience_years", "EXPERIENCE", "years_experience"),
        ("insurance_requirements", "INSURANCE", "insurance"),
        ("guarantee_requirements", "GUARANTEE", "guarantee"),
        ("workforce_requirements", "WORKFORCE", "workforce"),
        ("equipment_requirements", "EQUIPMENT", "equipment"),
        ("registration_requirements", "REGISTRATION", "registration"),
        ("document_requirements", "DOCUMENT", "document"),
        ("geographical_requirements", "GEOGRAPHY", "geography"),
        ("consortium_conditions", "CONSORTIUM", "consortium"),
    ],
)
def test_structured_categories(field_name, category, req_type):
    req = StructuredRequirementExtractor().extract(_ctx(**{field_name: "explicit source value"}))[0]
    assert req.category == category
    assert req.requirement_type == req_type
    assert req.priority == "MANDATORY"
    assert req.evidence[0].source_ref == "OFFICIAL"


def test_explicit_requirement_supports_mandatory_optional_preferred_unknown():
    requirements = [
        {"category": "DOCUMENT", "type": "declaration", "description": "A", "priority": "mandatory"},
        {"category": "DOCUMENT", "type": "brochure", "description": "B", "priority": "optional"},
        {"category": "TECHNICAL", "type": "method", "description": "C", "priority": "preferred"},
        {"category": "OTHER", "type": "other", "description": "D"},
    ]
    reqs = StructuredRequirementExtractor().extract(_ctx(requirements=requirements))
    assert {r.priority for r in reqs} == {"MANDATORY", "OPTIONAL", "PREFERRED", "UNKNOWN"}
    unknown = next(r for r in reqs if r.description == "D")
    assert unknown.mandatory is None


def test_no_missing_data_fabricates_requirement():
    assert StructuredRequirementExtractor().extract(_ctx()) == []
    assert build_checklist(_ctx()).requirements == ()


def test_duplicate_equivalent_requirement_merges_evidence():
    reqs = StructuredRequirementExtractor().extract(_ctx(requirements=[
        {"category": "CERTIFICATION", "type": "certification", "description": "ISO 9001 required", "value": "ISO 9001", "priority": "mandatory", "locator": "json:requirements[0]"},
        {"category": "CERTIFICATION", "type": "certification", "description": "ISO 9001 required", "value": "ISO 9001", "priority": "mandatory", "locator": "document:42:page:7"},
    ]))
    assert len(reqs) == 1
    assert len(reqs[0].evidence) == 2


def test_conflicting_requirements_are_not_silently_selected():
    one = _req(requirement_id="one", required_value=1_000_000)
    two = _req(requirement_id="two", required_value=2_000_000)
    reqs = consolidate_requirements([one, two])
    assert len(reqs) == 2
    assert all(r.status == "CONFLICT" for r in reqs)


def test_supersession_preserves_history():
    old = _req(requirement_id="old", required_value=1_000_000)
    new = _req(requirement_id="new", required_value=2_000_000)
    reqs = supersede([old, new], "old", "new")
    old_after = next(r for r in reqs if r.requirement_id == "old")
    new_after = next(r for r in reqs if r.requirement_id == "new")
    assert old_after.status == "SUPERSEDED"
    assert new_after.supersedes == "old"


def test_reprocessing_is_idempotent_and_requirement_id_is_stable():
    context = _ctx(required_certifications=["ISO 9001"])
    first = StructuredRequirementExtractor().extract(context)
    second = StructuredRequirementExtractor().extract(context)
    assert [r.requirement_id for r in first] == [r.requirement_id for r in second]
    assert len(consolidate_requirements(first + second)) == 1


def test_text_mention_does_not_become_mandatory_requirement():
    reqs = ConservativeTextRequirementExtractor().extract(_ctx(
        normalized_text="ISO 9001 is widely used in construction quality systems."
    ))
    assert reqs == []


def test_text_negation_does_not_become_requirement():
    reqs = ConservativeTextRequirementExtractor().extract(_ctx(
        normalized_text="The bidder is not required to hold ISO 9001."
    ))
    assert reqs == []


def test_previous_contractor_context_does_not_become_requirement():
    reqs = ConservativeTextRequirementExtractor().extract(_ctx(
        normalized_text="The previous contractor held certification ISO 9001."
    ))
    assert reqs == []


def test_explicit_bidder_obligation_can_create_medium_confidence_candidate_from_text():
    reqs = ConservativeTextRequirementExtractor().extract(_ctx(
        normalized_text="The bidder must hold ISO 9001 certification."
    ))
    assert len(reqs) == 1
    assert reqs[0].category == "CERTIFICATION"
    assert reqs[0].priority == "MANDATORY"
    assert reqs[0].confidence == "MEDIUM"
    assert reqs[0].evidence[0].extraction_method == "text_rule"


def test_missing_company_data_is_unknown_not_not_met():
    checklist = OpportunityRequirementsChecklist("opp-1", (_req(
        category="CERTIFICATION", requirement_type="certification",
        description="ISO 9001 required", required_value="ISO 9001", currency=None,
    ),))
    assessed = assess_checklist(checklist, None)
    assert assessed.assessments[0].eligibility == "UNKNOWN"
    assert assessed.assessments[0].known_blocker is False


def test_known_company_certification_is_met():
    checklist = OpportunityRequirementsChecklist("opp-1", (_req(
        category="CERTIFICATION", requirement_type="certification",
        description="ISO 9001 required", required_value="ISO 9001", currency=None,
    ),))
    assessed = assess_checklist(checklist, {"account_id": "tenant-a", "certifications": ["ISO 9001"]}, account_id="tenant-a")
    assert assessed.assessments[0].eligibility == "MET"


def test_nonmatching_recorded_certifications_remain_unknown_not_not_met():
    checklist = OpportunityRequirementsChecklist("opp-1", (_req(
        category="CERTIFICATION", requirement_type="certification",
        description="ISO 9001 required", required_value="ISO 9001", currency=None,
    ),))
    assessed = assess_checklist(checklist, {"account_id": "tenant-a", "certifications": ["ISO 14001"]}, account_id="tenant-a")
    assert assessed.assessments[0].eligibility == "UNKNOWN"
    assert assessed.assessments[0].known_blocker is False


def test_incomparable_company_fact_is_not_evaluated():
    checklist = OpportunityRequirementsChecklist("opp-1", (_req(),))
    assessed = assess_checklist(checklist, {"account_id": "tenant-a", "certifications": ["ISO 9001"]}, account_id="tenant-a")
    assert assessed.assessments[0].eligibility == "NOT_EVALUATED"


def test_company_assessment_rejects_cross_tenant_profile():
    checklist = OpportunityRequirementsChecklist("opp-1", (_req(
        category="CERTIFICATION", requirement_type="certification",
        description="ISO 9001 required", required_value="ISO 9001", currency=None,
    ),))
    with pytest.raises(PermissionError):
        assess_checklist(checklist, {"account_id": "tenant-b", "certifications": ["ISO 9001"]}, account_id="tenant-a")


def test_checklist_summary_exposes_unknowns_and_conflicts_without_binary_eligibility():
    checklist = OpportunityRequirementsChecklist("opp-1", (
        _req(requirement_id="a", priority="MANDATORY"),
        _req(requirement_id="b", category="DOCUMENT", requirement_type="brochure", priority="OPTIONAL", required_value="brochure", currency=None),
        _req(requirement_id="c", category="OTHER", requirement_type="unclear", priority="UNKNOWN", required_value="verify", currency=None, status="CONFLICT"),
    ))
    summary = checklist.to_dict()["summary"]
    assert summary["mandatory"] == 1
    assert summary["optional"] == 1
    assert summary["unknown_priority"] == 1
    assert summary["conflicts"] == 1
