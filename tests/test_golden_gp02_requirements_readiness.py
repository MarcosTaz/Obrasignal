from datetime import datetime, timezone

import pytest

from opportunity_readiness import TenantBoundaryError, evaluate_readiness
from readiness_requirements_adapter import resolve_requirements

FIXED_CLOCK = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
ECONOMIC_KNOWN = {
    "status": "FAVOURABLE",
    "reason": "Deterministic acceptance fixture; not a commercial recommendation.",
    "rule_version": "golden-gp02.fixture.v1",
}


def _opportunity(**overrides):
    item = {
        "id": 2002,
        "source": "TED",
        "external_id": "GP02-REQ-READY",
        "country": "PRT",
        "deadline": "2026-09-30T12:00:00+00:00",
        "is_actionable": True,
        "lifecycle_status": "OPEN",
    }
    item.update(overrides)
    return item


def _readiness(opportunity, company, requirements):
    return evaluate_readiness(
        "tenant-a",
        opportunity,
        company,
        requirements=requirements,
        economic_fit_result=ECONOMIC_KNOWN,
        clock=FIXED_CLOCK,
    )


def test_partial_positive_requirements_never_become_fully_ready():
    opportunity = _opportunity(required_certifications=["ISO 9001"])
    company = {"account_id": "tenant-a", "certifications": ["ISO 9001"]}

    requirements = resolve_requirements("tenant-a", opportunity, company)

    assert requirements is not None
    assert any(item["status"] == "MET" for item in requirements)
    coverage = next(item for item in requirements if item["code"] == "requirements_coverage_unverified")
    assert coverage["mandatory"] is True
    assert coverage["status"] == "UNKNOWN"

    result = _readiness(opportunity, company, requirements)
    assert result["overall_status"] == "UNKNOWN"
    assert result["overall_status"] != "READY"
    assert any(item["code"] == "requirement_unknown" for item in result["unknown_items"])
    assert "decision" not in result
    assert "pursue" not in {str(value).lower() for value in result.values() if isinstance(value, str)}


def test_missing_company_certification_fact_is_unknown_not_not_met():
    opportunity = _opportunity(required_certifications=["ISO 14001"])
    company = {"account_id": "tenant-a", "certifications": []}

    requirements = resolve_requirements("tenant-a", opportunity, company)

    assert requirements is not None
    evaluated = [item for item in requirements if item["code"] != "requirements_coverage_unverified"]
    assert evaluated
    assert all(item["status"] == "UNKNOWN" for item in evaluated)
    assert all(item["status"] != "NOT_MET" for item in evaluated)
    result = _readiness(opportunity, company, requirements)
    assert result["overall_status"] == "UNKNOWN"
    assert not result["blocking_items"]


def test_unsupported_company_fact_remains_unknown_in_real_combination():
    opportunity = _opportunity(
        workforce_requirements=[{"description": "Minimum 12 qualified installers", "mandatory": True}]
    )
    company = {"account_id": "tenant-a", "crew_count": 12}

    requirements = resolve_requirements("tenant-a", opportunity, company)

    assert requirements is not None
    evaluated = [item for item in requirements if item["code"] != "requirements_coverage_unverified"]
    assert evaluated
    assert all(item["status"] == "UNKNOWN" for item in evaluated)
    result = _readiness(opportunity, company, requirements)
    assert result["overall_status"] == "UNKNOWN"


def test_readiness_preserves_an_explicit_known_blocker_without_making_a_decision():
    opportunity = _opportunity()
    company = {"account_id": "tenant-a"}
    explicit_contract = [{
        "code": "required_registration",
        "name": "Required national registration",
        "mandatory": True,
        "status": "NOT_MET",
        "source_ref": "TED:GP02-REQ-READY",
        "evidence_ref": "TED:GP02-REQ-READY#requirements[0]",
    }]

    result = _readiness(opportunity, company, explicit_contract)

    assert result["overall_status"] == "NOT_READY"
    assert any(item["code"] == "mandatory_requirement_not_met" for item in result["blocking_items"])
    assert "decision" not in result


def test_requirements_adapter_fails_closed_when_tenant_profile_mismatches():
    opportunity = _opportunity(required_certifications=["ISO 9001"])
    mismatched = {"account_id": "tenant-b", "certifications": ["ISO 9001"]}

    assert resolve_requirements("tenant-a", opportunity, mismatched) is None
    with pytest.raises(TenantBoundaryError):
        evaluate_readiness(
            "tenant-a",
            opportunity,
            mismatched,
            requirements=None,
            economic_fit_result=ECONOMIC_KNOWN,
            clock=FIXED_CLOCK,
        )


def test_replay_same_inputs_and_clock_is_identical():
    opportunity = _opportunity(required_certifications=["ISO 9001"])
    company = {"account_id": "tenant-a", "certifications": ["ISO 9001"]}
    requirements = resolve_requirements("tenant-a", opportunity, company)

    first = _readiness(opportunity, company, requirements)
    second = _readiness(opportunity, company, requirements)

    assert first == second
    assert first["generated_at"] == "2026-08-25T12:00:00+00:00"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BUG-GP-READINESS-DATE-001: a date-only deadline string is coerced to an "
        "invented midnight UTC instant instead of preserving date precision and unknown timezone"
    ),
)
def test_date_only_deadline_cannot_become_an_exact_open_or_expired_instant():
    opportunity = _opportunity(deadline="2026-08-25")
    company = {"account_id": "tenant-a"}
    requirements = [{"name": "fixture requirement", "mandatory": True, "status": "MET"}]

    result = _readiness(opportunity, company, requirements)
    deadline = result["dimensions"]["DEADLINE"]

    # Product-truth contract: date precision without a source timezone cannot
    # support an invented exact instant, therefore the temporal state must stay
    # unresolved instead of being presented as definitively open or expired.
    assert deadline["status"] == "UNKNOWN"
    assert not any(
        item["code"] in {"submission_deadline_expired", "submission_deadline_valid"}
        for item in deadline["items"]
    )
