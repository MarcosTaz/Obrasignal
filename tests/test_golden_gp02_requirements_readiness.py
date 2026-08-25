from datetime import datetime, timedelta, timezone

import pytest

from company_state import CompanyFact, CompanyState, FactCategory, KnowledgeState, Provenance, ProvenanceBasis, TenantBoundaryError
from opportunity_readiness import evaluate_readiness
from readiness_requirements_adapter import resolve_requirements

FIXED_CLOCK = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
ECONOMIC_KNOWN = {"status": "FAVOURABLE", "reason": "Deterministic acceptance fixture; not a commercial recommendation.", "rule_version": "golden-gp02.fixture.v2"}


def _opportunity(**overrides):
    item = {"id": 2002, "source": "TED", "external_id": "GP02-REQ-READY", "country": "PRT", "deadline": "2026-09-30T12:00:00+00:00", "is_actionable": True, "lifecycle_status": "OPEN"}
    item.update(overrides)
    return item


def _state(*facts, account="tenant-a"):
    return CompanyState(account, FIXED_CLOCK, tuple(facts))


def _valid_iso():
    return CompanyFact(
        FactCategory.QUALIFICATION, "qualification.iso-9001", KnowledgeState.FACT,
        {"name": "ISO 9001", "status": "HELD", "validity": "VALID"},
        Provenance(ProvenanceBasis.VERIFIED, source_ref="registry", evidence_ref="evidence:iso9001", observed_at=FIXED_CLOCK, verified_at=FIXED_CLOCK),
        effective_until=FIXED_CLOCK + timedelta(days=365),
    )


def _readiness(opportunity, company, requirements):
    return evaluate_readiness(
        "tenant-a", opportunity,
        {"account_id": "tenant-a", "status": "AVAILABLE", "company_state_fingerprint": company.fingerprint},
        requirements=requirements, economic_fit_result=ECONOMIC_KNOWN, clock=FIXED_CLOCK,
    )


def test_partial_positive_requirements_never_become_fully_ready():
    opportunity = _opportunity(required_certifications=["ISO 9001"])
    company = _state(_valid_iso())
    requirements = resolve_requirements("tenant-a", opportunity, company)
    assert any(item["status"] == "MET" for item in requirements)
    coverage = next(item for item in requirements if item["code"] == "requirements_coverage_unverified")
    assert coverage["status"] == "UNKNOWN"
    result = _readiness(opportunity, company, requirements)
    assert result["overall_status"] == "UNKNOWN"
    assert result["overall_status"] != "READY"
    assert "decision" not in result


def test_missing_company_certification_fact_is_unknown_not_not_met():
    opportunity = _opportunity(required_certifications=["ISO 14001"])
    company = _state()
    requirements = resolve_requirements("tenant-a", opportunity, company)
    evaluated = [item for item in requirements if item["code"] != "requirements_coverage_unverified"]
    assert evaluated and all(item["status"] == "UNKNOWN" for item in evaluated)
    result = _readiness(opportunity, company, requirements)
    assert result["overall_status"] == "UNKNOWN"
    assert not result["blocking_items"]


def test_total_crew_does_not_substitute_for_available_crew():
    opportunity = _opportunity(requirements=[{"category": "WORKFORCE", "requirement_type": "available_crew", "description": "Minimum 12 available installers", "required_value": 12, "unit": "count", "mandatory": True}])
    total = CompanyFact(FactCategory.CAPACITY, "crew.total_count", KnowledgeState.FACT, 12, Provenance(ProvenanceBasis.DECLARED, source_ref="manual", observed_at=FIXED_CLOCK), unit="workers")
    company = _state(total)
    requirements = resolve_requirements("tenant-a", opportunity, company)
    evaluated = [item for item in requirements if item["code"] != "requirements_coverage_unverified"]
    assert evaluated[0]["status"] == "UNKNOWN"


def test_readiness_preserves_explicit_blocker_without_decision():
    opportunity = _opportunity()
    company = _state()
    contract = [{"code": "required_registration", "name": "Required national registration", "mandatory": True, "status": "NOT_MET", "source_ref": "TED:GP02-REQ-READY", "evidence_ref": "TED:GP02-REQ-READY#requirements[0]"}]
    result = _readiness(opportunity, company, contract)
    assert result["overall_status"] == "NOT_READY"
    assert any(item["code"] == "mandatory_requirement_not_met" for item in result["blocking_items"])
    assert "decision" not in result


def test_requirements_adapter_fails_closed_when_tenant_state_mismatches():
    with pytest.raises(TenantBoundaryError):
        resolve_requirements("tenant-a", _opportunity(required_certifications=["ISO 9001"]), _state(_valid_iso(), account="tenant-b"))


def test_replay_same_inputs_and_clock_is_identical():
    opportunity = _opportunity(required_certifications=["ISO 9001"])
    company = _state(_valid_iso())
    requirements = resolve_requirements("tenant-a", opportunity, company)
    first = _readiness(opportunity, company, requirements)
    second = _readiness(opportunity, company, requirements)
    assert first == second
    assert first["generated_at"] == "2026-08-25T12:00:00+00:00"


def test_date_only_deadline_cannot_become_an_exact_open_or_expired_instant():
    opportunity = _opportunity(deadline="2026-08-25")
    company = _state()
    result = _readiness(opportunity, company, [{"name": "fixture requirement", "mandatory": True, "status": "MET"}])
    deadline = result["dimensions"]["DEADLINE"]
    assert deadline["status"] == "UNKNOWN"
    assert deadline["items"][0]["temporal_precision"] == "DATE"
    assert not any(item["code"] in {"submission_deadline_expired", "submission_deadline_valid"} for item in deadline["items"])
