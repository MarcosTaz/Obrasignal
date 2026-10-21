from datetime import datetime, timedelta, timezone

import pytest

from company_state import (
    CompanyFact,
    CompanyState,
    FactCategory,
    KnowledgeState,
    Provenance,
    ProvenanceBasis,
    TenantBoundaryError,
)
from company_state_profile_adapter import company_state_from_profile
from opportunity_readiness import evaluate_readiness
from readiness_requirements_adapter import resolve_requirements

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
ECONOMIC = {"status": "FAVOURABLE", "reason": "fixture", "rule_version": "fixture.v1"}


def _opportunity(**overrides):
    value = {
        "id": 901,
        "source": "TED",
        "external_id": "OPS-901",
        "country": "PRT",
        "deadline": "2026-09-30T12:00:00+00:00",
        "is_actionable": True,
        "lifecycle_status": "OPEN",
    }
    value.update(overrides)
    return value


def _state(*facts, account="tenant-a"):
    return CompanyState(account, NOW, tuple(facts))


def _prov(*, basis=ProvenanceBasis.VERIFIED, evidence="evidence:company:1"):
    return Provenance(
        basis,
        source_ref="company-registry",
        evidence_ref=evidence if basis is ProvenanceBasis.VERIFIED else None,
        observed_at=NOW,
        verified_at=NOW if basis is ProvenanceBasis.VERIFIED else None,
    )


def _cert(value, *, knowledge=KnowledgeState.FACT, effective_until=None, basis=ProvenanceBasis.VERIFIED):
    return CompanyFact(
        category=FactCategory.QUALIFICATION,
        code="qualification.iso-9001",
        knowledge=knowledge,
        value=value,
        provenance=_prov(basis=basis),
        effective_until=effective_until,
    )


def _resolved(opportunity, state):
    items = resolve_requirements("tenant-a", opportunity, state)
    assert items is not None
    return [item for item in items if item["code"] != "requirements_coverage_unverified"]


def test_current_verified_certification_can_be_met_and_preserves_both_evidence_bases():
    state = _state(_cert(
        {"name": "ISO 9001", "status": "HELD", "validity": "VALID"},
        effective_until=NOW + timedelta(days=90),
    ))
    items = _resolved(_opportunity(required_certifications=["ISO 9001"]), state)
    assert items[0]["status"] == "MET"
    assert items[0]["company_fact_ids"]
    assert "evidence:company:1" in items[0]["evidence_refs"]
    assert any(ref.startswith("TED:OPS-901#") for ref in items[0]["evidence_refs"])


def test_missing_certification_is_unknown_not_not_met():
    items = _resolved(_opportunity(required_certifications=["ISO 9001"]), _state())
    assert items[0]["status"] == "UNKNOWN"


def test_recorded_certification_with_unknown_validity_is_unknown():
    declared = _cert(
        {"name": "ISO 9001", "status": "DECLARED_HELD", "validity": "UNKNOWN"},
        basis=ProvenanceBasis.DECLARED,
    )
    items = _resolved(_opportunity(required_certifications=["ISO 9001"]), _state(declared))
    assert items[0]["status"] == "UNKNOWN"
    assert "validity" in items[0]["reason"].lower()


def test_expired_certification_is_known_not_met_not_missing():
    expired = _cert(
        {"name": "ISO 9001", "status": "HELD", "validity": "VALID"},
        effective_until=NOW - timedelta(seconds=1),
    )
    items = _resolved(_opportunity(required_certifications=["ISO 9001"]), _state(expired))
    assert items[0]["status"] == "NOT_MET"
    assert "expired" in items[0]["reason"].lower()


def test_conflicting_current_certification_facts_remain_conflict():
    first = _cert(
        {"name": "ISO 9001", "status": "HELD", "validity": "VALID"},
        effective_until=NOW + timedelta(days=30),
        basis=ProvenanceBasis.VERIFIED,
    )
    second = CompanyFact(
        category=FactCategory.QUALIFICATION,
        code="qualification.iso-9001",
        knowledge=KnowledgeState.FACT,
        value={"name": "ISO 9001", "status": "NOT_HELD", "validity": "INVALID"},
        provenance=Provenance(
            ProvenanceBasis.INTEGRATION,
            source_ref="office",
            observed_at=NOW,
        ),
        effective_until=NOW + timedelta(days=30),
    )
    items = _resolved(_opportunity(required_certifications=["ISO 9001"]), _state(first, second))
    assert items[0]["status"] == "CONFLICT"


def _crew_fact(value, *, knowledge=KnowledgeState.FACT):
    return CompanyFact(
        category=FactCategory.AVAILABILITY,
        code="crew.available_count",
        knowledge=knowledge,
        value=value if knowledge is not KnowledgeState.UNKNOWN else None,
        unit="workers",
        provenance=(
            _prov(basis=ProvenanceBasis.INTEGRATION, evidence=None)
            if knowledge is not KnowledgeState.UNKNOWN
            else Provenance(ProvenanceBasis.UNAVAILABLE, source_ref="office:not-known", observed_at=NOW)
        ),
        effective_from=NOW - timedelta(hours=1),
        effective_until=NOW + timedelta(days=7),
    )


def _crew_requirement(minimum):
    return _opportunity(requirements=[{
        "category": "WORKFORCE",
        "requirement_type": "available_crew",
        "description": f"At least {minimum} available workers",
        "required_value": minimum,
        "unit": "count",
        "mandatory": True,
    }])


def test_trade_and_total_headcount_do_not_substitute_for_available_crew():
    facts = (
        CompanyFact(
            FactCategory.CAPABILITY, "capability.drywall", KnowledgeState.FACT,
            {"label": "Drywall"}, _prov(basis=ProvenanceBasis.DECLARED, evidence=None),
        ),
        CompanyFact(
            FactCategory.CAPACITY, "crew.total_count", KnowledgeState.FACT,
            12, _prov(basis=ProvenanceBasis.DECLARED, evidence=None), unit="workers",
        ),
    )
    items = _resolved(_crew_requirement(3), _state(*facts))
    assert items[0]["status"] == "UNKNOWN"
    assert "total headcount" in items[0]["reason"].lower()


def test_known_zero_available_crew_is_not_met():
    items = _resolved(_crew_requirement(1), _state(_crew_fact(0)))
    assert items[0]["status"] == "NOT_MET"


def test_unknown_available_crew_stays_unknown():
    items = _resolved(_crew_requirement(1), _state(_crew_fact(None, knowledge=KnowledgeState.UNKNOWN)))
    assert items[0]["status"] == "UNKNOWN"


def test_known_available_crew_can_meet_numeric_requirement():
    items = _resolved(_crew_requirement(3), _state(_crew_fact(4)))
    assert items[0]["status"] == "MET"


def test_known_operational_wrong_geography_is_not_met():
    operating = CompanyFact(
        FactCategory.GEOGRAPHY,
        "geography.operating_countries",
        KnowledgeState.FACT,
        ["PRT"],
        _prov(basis=ProvenanceBasis.DECLARED, evidence=None),
    )
    items = _resolved(_opportunity(geographical_requirements=["ESP"]), _state(operating))
    assert items[0]["status"] == "NOT_MET"


def test_preferred_geography_only_never_becomes_operational_eligibility():
    profile_state = company_state_from_profile(
        {"account_id": "tenant-a", "countries": ["ESP"]},
        account_id="tenant-a",
        as_of=NOW,
    )
    items = _resolved(_opportunity(geographical_requirements=["ESP"]), profile_state)
    assert items[0]["status"] == "UNKNOWN"


def test_cross_tenant_company_state_fails_closed():
    wrong = _state(account="tenant-b")
    with pytest.raises(TenantBoundaryError):
        resolve_requirements("tenant-a", _opportunity(required_certifications=["ISO 9001"]), wrong)


def _readiness(deadline, **extra):
    opportunity = _opportunity(deadline=deadline, **extra)
    return evaluate_readiness(
        "tenant-a",
        opportunity,
        {"account_id": "tenant-a", "status": "AVAILABLE"},
        requirements=[{"name": "fixture", "mandatory": True, "status": "MET"}],
        economic_fit_result=ECONOMIC,
        clock=NOW,
    )


@pytest.mark.parametrize(
    ("deadline", "precision"),
    [
        ("2026-08-25", "DATE"),
        ("2026-08", "MONTH"),
        ("2026-Q3", "QUARTER"),
        ("2026", "YEAR"),
    ],
)
def test_imprecise_deadline_never_becomes_exact_open_or_expired(deadline, precision):
    result = _readiness(deadline)
    dimension = result["dimensions"]["DEADLINE"]
    assert dimension["status"] == "UNKNOWN"
    item = dimension["items"][0]
    assert item["temporal_precision"] == precision
    assert not any(
        value["code"] in {"submission_deadline_valid", "submission_deadline_expired"}
        for value in dimension["items"]
    )


def test_datetime_without_timezone_remains_unknown_timezone():
    result = _readiness("2026-08-26T12:00:00")
    item = result["dimensions"]["DEADLINE"]["items"][0]
    assert item["code"] == "submission_deadline_timezone_unknown"
    assert item["temporal_precision"] == "DATETIME"
    assert item["timezone_status"] == "UNKNOWN"
    assert result["overall_status"] == "UNKNOWN"


def test_datetime_with_explicit_timezone_can_be_evaluated_without_inventing_one():
    result = _readiness("2026-08-26T12:00:00", deadline_timezone="Europe/Lisbon")
    item = result["dimensions"]["DEADLINE"]["items"][0]
    assert item["code"] == "submission_deadline_valid"
    assert item["timezone_status"] == "KNOWN"


def test_partial_positive_requirements_cannot_make_ready():
    state = _state(_cert(
        {"name": "ISO 9001", "status": "HELD", "validity": "VALID"},
        effective_until=NOW + timedelta(days=90),
    ))
    opportunity = _opportunity(required_certifications=["ISO 9001"])
    requirements = resolve_requirements("tenant-a", opportunity, state)
    result = evaluate_readiness(
        "tenant-a",
        opportunity,
        {"account_id": "tenant-a", "status": "AVAILABLE"},
        requirements=requirements,
        economic_fit_result=ECONOMIC,
        clock=NOW,
    )
    assert any(item["requirement_status"] == "MET" for item in result["ready_items"])
    assert result["overall_status"] == "UNKNOWN"
    assert result["overall_status"] != "READY"


def test_requirement_conflict_is_visible_and_never_ready():
    opportunity = _opportunity(requirements=[
        {
            "category": "CERTIFICATION",
            "requirement_type": "certification",
            "description": "ISO requirement",
            "required_value": "ISO 9001",
            "mandatory": True,
        },
        {
            "category": "CERTIFICATION",
            "requirement_type": "certification",
            "description": "ISO requirement",
            "required_value": "ISO 14001",
            "mandatory": True,
        },
    ])
    requirements = resolve_requirements("tenant-a", opportunity, _state())
    assert any(item["status"] == "CONFLICT" for item in requirements)
    result = evaluate_readiness(
        "tenant-a", opportunity, {"account_id": "tenant-a", "status": "AVAILABLE"},
        requirements=requirements, economic_fit_result=ECONOMIC, clock=NOW,
    )
    assert result["conflict_items"]
    assert result["overall_status"] == "UNKNOWN"


def test_evidence_contract_is_explicitly_unavailable_without_importing_q080():
    result = _readiness("2026-09-30T12:00:00+00:00")
    assert result["evidence_contract"]["status"] == "UNAVAILABLE"
    assert result["evidence_contract"]["contract"] == "evidence-graph.v1"


def test_readiness_never_emits_pursuit_decision_vocabulary():
    result = _readiness("2026-09-30T12:00:00+00:00")
    assert "decision" not in result
    assert "pursue" not in result
    assert "no_bid" not in result
