from datetime import datetime, timezone
from decimal import Decimal
import pytest

from company_state import FactCategory, KnowledgeState, TenantBoundaryError
from company_state_adapters import requirements_facts
from company_state_profile_adapter import company_state_from_profile

NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)


def fact_by_code(state, code):
    return next(fact for fact in state.facts if fact.code == code)


def test_profile_adapter_reuses_capabilities_without_replacing_profile():
    profile = {
        "account_id": "a",
        "services": ["Pintura"],
        "capability_tags": ["pintura", "Pladur"],
        "certifications": ["ISO 9001"],
        "regions": ["Leiria"],
        "countries": ["PRT"],
        "geographic_radius_km": 100,
        "min_value": 100000.0,
        "max_value": 500000.0,
    }
    state = company_state_from_profile(profile, account_id="a", as_of=NOW)
    assert state.account_id == "a"
    assert len([f for f in state.facts if f.category is FactCategory.CAPABILITY]) == 2
    qualification = [f for f in state.facts if f.category is FactCategory.QUALIFICATION][0]
    assert qualification.value["status"] == "DECLARED_HELD"
    assert qualification.value["validity"] == "UNKNOWN"
    # Commercial target range is not operational financial capacity and profile
    # has no explicit currency; it must not be imported as Money.
    assert not any(f.category is FactCategory.FINANCIAL_CONSTRAINT for f in state.facts)


def test_legacy_default_portugal_is_preference_assumption_not_operating_fact():
    state = company_state_from_profile({"account_id": "a", "countries": ["PRT"]}, account_id="a", as_of=NOW)
    preferred = fact_by_code(state, "geography.preferred_countries")
    operating = fact_by_code(state, "geography.operating_countries")
    assert preferred.knowledge is KnowledgeState.ASSUMPTION
    assert preferred.value == ["PRT"]
    assert operating.knowledge is KnowledgeState.UNKNOWN
    assert operating.value is None


def test_explicit_profile_geography_is_preference_not_operational_capability():
    state = company_state_from_profile(
        {"account_id": "a", "countries": ["ESP"], "regions": ["Madrid"]},
        account_id="a",
        as_of=NOW,
    )
    preferred_countries = fact_by_code(state, "geography.preferred_countries")
    preferred_regions = fact_by_code(state, "geography.preferred_regions")
    operating = fact_by_code(state, "geography.operating_countries")
    assert preferred_countries.knowledge is KnowledgeState.FACT
    assert preferred_countries.value == ["ESP"]
    assert preferred_regions.knowledge is KnowledgeState.FACT
    assert preferred_regions.value == ["Madrid"]
    assert operating.knowledge is KnowledgeState.UNKNOWN
    assert state.single_current_value("geography.operating_countries") is None
    assert "geography.operating_countries" in state.unknowns()


def test_requirements_seam_excludes_commercial_geography_preferences():
    state = company_state_from_profile(
        {
            "account_id": "a",
            "countries": ["ESP"],
            "regions": ["Madrid"],
            "geographic_radius_km": 75,
            "services": ["Pintura"],
        },
        account_id="a",
        as_of=NOW,
    )
    projected = requirements_facts(state)["facts"]
    codes = {fact["code"] for fact in projected}
    assert "geography.preferred_countries" not in codes
    assert "geography.preferred_regions" not in codes
    assert "geography.operating_countries" in codes
    assert "geography.practical_radius_km" in codes
    assert "capability.pintura" in codes


def test_missing_profile_fields_produce_partial_state_with_explicit_unknowns():
    state = company_state_from_profile({"account_id": "a"}, account_id="a", as_of=NOW)
    assert set(state.unknowns()) == {
        "crew.total_count",
        "crew.available_count",
        "vehicle.available_count",
        "geography.base",
        "geography.operating_countries",
    }
    assert all(f.knowledge is KnowledgeState.UNKNOWN for f in state.facts)


def test_adapter_rejects_cross_tenant_profile():
    with pytest.raises(TenantBoundaryError):
        company_state_from_profile({"account_id": "b", "services": ["painting"]}, account_id="a", as_of=NOW)


def test_float_radius_is_losslessly_projected_as_decimal_not_binary_float():
    state = company_state_from_profile({"account_id": "a", "geographic_radius_km": 12.5}, account_id="a", as_of=NOW)
    radius = fact_by_code(state, "geography.practical_radius_km")
    assert radius.value == Decimal("12.5")
