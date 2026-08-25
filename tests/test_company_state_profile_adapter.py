from datetime import datetime, timezone
from decimal import Decimal
import pytest

from company_state import FactCategory, KnowledgeState, TenantBoundaryError
from company_state_profile_adapter import company_state_from_profile

NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)


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


def test_legacy_default_portugal_is_assumption_not_fact():
    state = company_state_from_profile({"account_id": "a", "countries": ["PRT"]}, account_id="a", as_of=NOW)
    geo = [f for f in state.facts if f.code == "geography.operating_countries"][0]
    assert geo.knowledge is KnowledgeState.ASSUMPTION


def test_explicit_region_makes_geography_declared_fact():
    state = company_state_from_profile({"account_id": "a", "countries": ["PRT"], "regions": ["Leiria"]}, account_id="a", as_of=NOW)
    geo = [f for f in state.facts if f.code == "geography.operating_countries"][0]
    assert geo.knowledge is KnowledgeState.FACT


def test_missing_profile_fields_produce_partial_state_with_explicit_unknowns():
    state = company_state_from_profile({"account_id": "a"}, account_id="a", as_of=NOW)
    assert set(state.unknowns()) == {
        "crew.total_count", "crew.available_count", "vehicle.available_count", "geography.base"
    }
    assert all(f.knowledge is KnowledgeState.UNKNOWN for f in state.facts)


def test_adapter_rejects_cross_tenant_profile():
    with pytest.raises(TenantBoundaryError):
        company_state_from_profile({"account_id": "b", "services": ["painting"]}, account_id="a", as_of=NOW)


def test_float_radius_is_losslessly_projected_as_decimal_not_binary_float():
    state = company_state_from_profile({"account_id": "a", "geographic_radius_km": 12.5}, account_id="a", as_of=NOW)
    radius = [f for f in state.facts if f.code == "geography.practical_radius_km"][0]
    assert radius.value == Decimal("12.5")
