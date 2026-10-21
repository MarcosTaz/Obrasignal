from datetime import datetime, timedelta, timezone

from company_state import (
    CompanyFact,
    CompanyState,
    FactCategory,
    KnowledgeState,
    Provenance,
    ProvenanceBasis,
)
from company_state_adapters import economics_constraints, mobilize_inputs, requirements_facts

NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)
DECLARED = Provenance(ProvenanceBasis.DECLARED, source_ref="manual", observed_at=NOW)
UNAVAILABLE = Provenance(ProvenanceBasis.UNAVAILABLE, source_ref="not-provided", observed_at=NOW)


def test_realistic_small_contractor_state_improves_decisions_with_few_material_facts():
    facts = (
        CompanyFact(FactCategory.CAPABILITY, "capability.painting", KnowledgeState.FACT, {"label": "Painting"}, DECLARED),
        CompanyFact(FactCategory.GEOGRAPHY, "geography.base", KnowledgeState.FACT, {"country": "PRT", "region": "Leiria"}, DECLARED),
        CompanyFact(FactCategory.CAPACITY, "crew.total_count", KnowledgeState.FACT, 10, DECLARED, unit="workers"),
        CompanyFact(
            FactCategory.AVAILABILITY,
            "crew.available_count",
            KnowledgeState.FACT,
            6,
            DECLARED,
            unit="workers",
            effective_from=NOW,
            effective_until=NOW + timedelta(days=21),
        ),
        CompanyFact(
            FactCategory.AVAILABILITY,
            "vehicle.available_count",
            KnowledgeState.FACT,
            1,
            DECLARED,
            unit="vehicles",
            effective_until=NOW + timedelta(days=21),
        ),
        CompanyFact(FactCategory.QUALIFICATION, "qualification.iso-9001", KnowledgeState.UNKNOWN, None, UNAVAILABLE),
        CompanyFact(FactCategory.FINANCIAL_CONSTRAINT, "finance.maximum_cash_exposure", KnowledgeState.UNKNOWN, None, UNAVAILABLE),
    )
    state = CompanyState("contractor-a", NOW, facts)

    mobilize = mobilize_inputs(state)
    assert mobilize["workers"]["state"] == "KNOWN"
    assert mobilize["workers"]["value"] == 6
    assert mobilize["own_vehicles_available"]["value"] == 1
    assert mobilize["base_location"]["value"] == {"country": "PRT", "region": "Leiria"}

    requirements = requirements_facts(state)
    assert any(fact["code"] == "capability.painting" for fact in requirements["facts"])
    assert any(fact["code"] == "qualification.iso-9001" and fact["knowledge"] == "UNKNOWN" for fact in requirements["facts"])

    economics = economics_constraints(state)
    assert economics["maximum_cash_exposure"]["state"] == "UNKNOWN"
    assert economics["maximum_cash_exposure"]["value"] is None
    assert "decision" not in economics and "no_bid" not in economics


def test_minimal_trade_and_base_state_is_valid_and_missing_data_stays_unknown():
    state = CompanyState(
        "contractor-minimal",
        NOW,
        (
            CompanyFact(FactCategory.CAPABILITY, "capability.drywall", KnowledgeState.FACT, {"label": "Drywall"}, DECLARED),
            CompanyFact(FactCategory.GEOGRAPHY, "geography.base", KnowledgeState.FACT, {"country": "PRT", "region": "Leiria"}, DECLARED),
        ),
    )

    mobilize = mobilize_inputs(state)
    assert mobilize["workers"]["state"] == "UNKNOWN"
    assert mobilize["workers"]["reason"] == "fact_not_recorded"
    assert mobilize["own_vehicles_available"]["state"] == "UNKNOWN"
    assert mobilize["base_location"]["state"] == "KNOWN"

    economics = economics_constraints(state)
    assert economics["maximum_cash_exposure"]["state"] == "UNKNOWN"
    assert economics["working_capital_limit"]["state"] == "UNKNOWN"
    assert economics["guarantee_limit"]["state"] == "UNKNOWN"

    requirement_codes = {fact["code"] for fact in requirements_facts(state)["facts"]}
    assert "capability.drywall" in requirement_codes
    assert not any(code.startswith("qualification.") for code in requirement_codes)
    assert not any(code.startswith("equipment.") for code in requirement_codes)


def test_same_semantic_state_and_same_clock_replays_identically():
    first = CompanyState(
        "contractor-a",
        NOW,
        (
            CompanyFact(FactCategory.CAPABILITY, "capability.painting", KnowledgeState.FACT, True, DECLARED),
            CompanyFact(FactCategory.GEOGRAPHY, "geography.base", KnowledgeState.FACT, "Leiria", DECLARED),
        ),
    )
    second = CompanyState("contractor-a", NOW, tuple(reversed(first.facts)))
    assert first.fingerprint == second.fingerprint
    assert first.to_dict() == second.to_dict()
