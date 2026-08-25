import sys
from datetime import datetime, timezone
from types import SimpleNamespace

from opportunity_readiness import evaluate_readiness
from readiness_requirements_adapter import resolve_requirements

NOW = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)


def _fake_module(monkeypatch, assessments, *, coverage_complete=False):
    checklist = SimpleNamespace(requirements=(), coverage_complete=coverage_complete)
    assessed = SimpleNamespace(assessments=tuple(assessments), coverage_complete=coverage_complete)
    module = SimpleNamespace(
        build_checklist=lambda context, include_text_rules=False: checklist,
        assess_checklist=lambda value, profile, account_id=None: assessed,
    )
    monkeypatch.setitem(sys.modules, "opportunity_requirements", module)


def _assessment(*, priority="MANDATORY", eligibility="MET", known_blocker=False):
    evidence = SimpleNamespace(source_ref="TED:ABC", locator="requirements[0]")
    requirement = SimpleNamespace(
        requirement_id="req-1",
        priority=priority,
        description="ISO 9001 obrigatório",
        requirement_type="certification",
        evidence=(evidence,),
    )
    return SimpleNamespace(
        requirement=requirement,
        eligibility=eligibility,
        known_blocker=known_blocker,
    )


def _opportunity(**extra):
    value = {
        "id": 1,
        "source": "TED",
        "external_id": "ABC",
        "is_actionable": 1,
        "lifecycle_status": "OPEN",
        "deadline": "2026-09-05T12:00:00+00:00",
        "value": 100000,
    }
    value.update(extra)
    return value


def _evaluate(requirements):
    return evaluate_readiness(
        "acct-a",
        _opportunity(),
        {"account_id": "acct-a"},
        requirements=requirements,
        economic_fit_result={"status": "FAVOURABLE", "reason": "ok", "rule_version": "economic-fit-v2"},
        clock=NOW,
    )


def test_no_structured_requirements_input_stays_unavailable_even_if_module_exists(monkeypatch):
    _fake_module(monkeypatch, [_assessment()])
    result = resolve_requirements(
        "acct-a",
        {"id": 1, "source": "TED", "external_id": "ABC", "description": "bidder must have ISO 9001"},
        {"account_id": "acct-a"},
    )
    assert result is None


def test_explicit_structured_input_maps_public_assessment_and_keeps_coverage_unknown(monkeypatch):
    _fake_module(monkeypatch, [_assessment()])
    result = resolve_requirements(
        "acct-a",
        {"id": 1, "source": "TED", "external_id": "ABC", "requirements": [{"description": "ISO 9001"}]},
        {"account_id": "acct-a"},
    )
    assert result[0] == {
        "code": "req-1",
        "name": "ISO 9001 obrigatório",
        "mandatory": True,
        "status": "MET",
        "source_ref": "TED:ABC",
        "evidence_ref": "TED:ABC#requirements[0]",
    }
    assert result[-1]["code"] == "requirements_coverage_unverified"
    assert result[-1]["status"] == "UNKNOWN"
    assert result[-1]["mandatory"] is True


def test_partial_requirements_with_verified_fact_cannot_promote_ready(monkeypatch):
    _fake_module(monkeypatch, [_assessment(eligibility="MET")])
    requirements = resolve_requirements(
        "acct-a",
        _opportunity(requirements=[{"description": "ISO 9001"}]),
        {"account_id": "acct-a"},
    )
    result = _evaluate(requirements)
    assert result["overall_status"] == "UNKNOWN"
    assert any(item["description"].startswith("Requirement still unverified: Complete mandatory-requirements coverage") for item in result["unknown_items"])


def test_partial_requirements_known_blocker_still_makes_not_ready(monkeypatch):
    _fake_module(monkeypatch, [_assessment(eligibility="UNKNOWN", known_blocker=True)])
    requirements = resolve_requirements(
        "acct-a",
        _opportunity(required_certifications=["ISO 9001"]),
        {"account_id": "acct-a"},
    )
    result = _evaluate(requirements)
    assert result["overall_status"] == "NOT_READY"
    assert any(item["code"] == "mandatory_requirement_not_met" for item in result["blocking_items"])


def test_future_explicit_complete_coverage_removes_synthetic_unknown(monkeypatch):
    _fake_module(monkeypatch, [_assessment()], coverage_complete=True)
    result = resolve_requirements(
        "acct-a",
        {"external_id": "ABC", "source": "TED", "requirements": [{"description": "ISO 9001"}]},
        {"account_id": "acct-a"},
    )
    assert len(result) == 1
    assert result[0]["status"] == "MET"


def test_not_evaluated_requirement_maps_to_unknown_not_pass(monkeypatch):
    _fake_module(monkeypatch, [_assessment(eligibility="NOT_EVALUATED")])
    result = resolve_requirements(
        "acct-a",
        {"external_id": "ABC", "source": "TED", "minimum_turnover": 100000},
        {"account_id": "acct-a"},
    )
    assert result[0]["status"] == "UNKNOWN"
    assert result[0]["mandatory"] is True


def test_unknown_priority_remains_mandatory_conservative(monkeypatch):
    _fake_module(monkeypatch, [_assessment(priority="UNKNOWN", eligibility="UNKNOWN")])
    result = resolve_requirements(
        "acct-a",
        {"external_id": "ABC", "source": "TED", "requirements": [{"description": "unknown priority"}]},
        {"account_id": "acct-a"},
    )
    assert result[0]["mandatory"] is True
    assert result[0]["status"] == "UNKNOWN"


def test_known_blocker_maps_to_not_met(monkeypatch):
    _fake_module(monkeypatch, [_assessment(eligibility="UNKNOWN", known_blocker=True)])
    result = resolve_requirements(
        "acct-a",
        {"external_id": "ABC", "source": "TED", "required_certifications": ["ISO 9001"]},
        {"account_id": "acct-a"},
    )
    assert result[0]["status"] == "NOT_MET"
    assert result[-1]["code"] == "requirements_coverage_unverified"


def test_requirements_assessment_failure_degrades_to_unavailable(monkeypatch):
    module = SimpleNamespace(
        build_checklist=lambda context, include_text_rules=False: SimpleNamespace(requirements=()),
        assess_checklist=lambda value, profile, account_id=None: (_ for _ in ()).throw(PermissionError("tenant mismatch")),
    )
    monkeypatch.setitem(sys.modules, "opportunity_requirements", module)
    result = resolve_requirements(
        "acct-a",
        {"external_id": "ABC", "source": "TED", "requirements": []},
        {"account_id": "acct-a"},
    )
    assert result is None
