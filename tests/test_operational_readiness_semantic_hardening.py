from datetime import datetime, timezone

from company_state import CompanyFact, CompanyState, FactCategory, KnowledgeState, Provenance, ProvenanceBasis
from readiness_requirements_adapter import resolve_requirements

NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)


def _opportunity(requirement):
    return {
        "id": 990,
        "source": "TED",
        "external_id": "HARDEN-990",
        "requirements": [requirement],
    }


def _state(*facts):
    return CompanyState("tenant-a", NOW, tuple(facts))


def _evaluated(opportunity, state):
    result = resolve_requirements("tenant-a", opportunity, state)
    assert result is not None
    return next(item for item in result if item["code"] != "requirements_coverage_unverified")


def test_unanchored_negative_certification_fact_is_unknown_not_not_met():
    fact = CompanyFact(
        FactCategory.QUALIFICATION,
        "qualification.iso-9001",
        KnowledgeState.FACT,
        {"name": "ISO 9001", "status": "NOT_HELD", "validity": "INVALID"},
        Provenance(ProvenanceBasis.DECLARED, source_ref="manual", observed_at=NOW),
    )
    requirement = {
        "category": "CERTIFICATION",
        "requirement_type": "certification",
        "description": "ISO 9001 required",
        "required_value": "ISO 9001",
        "mandatory": True,
    }
    result = _evaluated(_opportunity(requirement), _state(fact))
    assert result["status"] == "UNKNOWN"
    assert "freshness" in result["reason"].lower() or "current" in result["reason"].lower()


def test_unsupported_workforce_operator_is_not_evaluated_instead_of_reversed():
    available = CompanyFact(
        FactCategory.AVAILABILITY,
        "crew.available_count",
        KnowledgeState.FACT,
        4,
        Provenance(ProvenanceBasis.INTEGRATION, source_ref="office", observed_at=NOW),
        unit="workers",
        freshness_until=datetime(2026, 8, 26, 12, tzinfo=timezone.utc),
    )
    requirement = {
        "category": "WORKFORCE",
        "requirement_type": "available_crew",
        "description": "No more than 3 available workers",
        "required_value": 3,
        "operator": "<=",
        "unit": "count",
        "mandatory": True,
    }
    result = _evaluated(_opportunity(requirement), _state(available))
    assert result["status"] == "NOT_EVALUATED"


def test_ambiguous_numeric_workforce_requirement_without_minimum_semantics_is_not_evaluated():
    available = CompanyFact(
        FactCategory.AVAILABILITY,
        "crew.available_count",
        KnowledgeState.FACT,
        4,
        Provenance(ProvenanceBasis.INTEGRATION, source_ref="office", observed_at=NOW),
        unit="workers",
        freshness_until=datetime(2026, 8, 26, 12, tzinfo=timezone.utc),
    )
    requirement = {
        "category": "WORKFORCE",
        "requirement_type": "available_crew",
        "description": "3 available workers",
        "required_value": 3,
        "unit": "count",
        "mandatory": True,
    }
    result = _evaluated(_opportunity(requirement), _state(available))
    assert result["status"] == "NOT_EVALUATED"
