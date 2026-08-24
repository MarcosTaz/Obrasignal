from global_market_portfolio import (
    GLOBAL_MARKET_PORTFOLIO,
    commercially_active_markets,
    dedicated_engineering_allowed,
    portfolio_counts,
    portfolio_market,
    tech_lab_markets,
)
from market_scope_registry import DEDICATED_CONNECTORS, TARGET_DEDICATED_CONNECTORS


def test_vnext_counts_preserve_full_universe_and_active_coverage():
    assert len(GLOBAL_MARKET_PORTFOLIO) == 135
    assert portfolio_counts() == {
        "BUILD": 14,
        "SHARED": 31,
        "TECH_LAB": 3,
        "HOLD": 26,
        "REMOVE": 61,
    }
    assert len(commercially_active_markets()) == 45


def test_dedicated_engineering_is_build_only_and_target_is_unchanged():
    assert len(DEDICATED_CONNECTORS) == TARGET_DEDICATED_CONNECTORS == 13
    assert all(dedicated_engineering_allowed(country) for country in DEDICATED_CONNECTORS)
    assert all(
        not market.dedicated_connector_required
        for market in GLOBAL_MARKET_PORTFOLIO.values()
        if market.category != "BUILD"
    )


def test_tech_labs_are_research_only_not_commercial_scope_inflation():
    assert tech_lab_markets() == ("Tanzania", "Uganda", "Zambia")
    for country in tech_lab_markets():
        market = portfolio_market(country)
        assert market.category == "TECH_LAB"
        assert not market.dedicated_connector_required
        assert country not in commercially_active_markets()


def test_uganda_and_zambia_preserve_technical_value_without_build_promotion():
    uganda = portfolio_market("Uganda")
    zambia = portfolio_market("Zambia")
    assert "procurement plans" in uganda.decision_reason
    assert "contract-award lifecycle" in uganda.decision_reason
    assert "OCDS" in zambia.decision_reason
    assert uganda.category == zambia.category == "TECH_LAB"


def test_namibia_is_hold_because_digital_procurement_exists_but_roi_is_not_proven():
    namibia = portfolio_market("Namibia")
    assert namibia.category == "HOLD"
    assert "official digital procurement" in namibia.decision_reason
    assert "opportunity cost" in namibia.decision_reason
    assert not namibia.dedicated_connector_required


def test_cabo_verde_remove_is_economic_not_false_data_absence_claim():
    cabo_verde = portfolio_market("Cabo Verde")
    assert cabo_verde.category == "REMOVE"
    assert "e-Compras" in cabo_verde.decision_reason
    assert "economic-priority" in cabo_verde.decision_reason
    assert "not a data-absence claim" in cabo_verde.decision_reason


def test_hold_bias_does_not_destroy_near_zero_cost_ted_coverage():
    assert portfolio_market("Norway").category == "SHARED"
    assert portfolio_market("Sweden").category == "SHARED"
    assert portfolio_market("Norway").connector_family == "TED_EFORMS"
    assert portfolio_market("Sweden").connector_family == "TED_EFORMS"


def test_korea_remains_hold_despite_prebuilt_connector():
    korea = portfolio_market("South Korea")
    assert korea.category == "HOLD"
    assert "KONEPS_SERVICE_KEY" in korea.reconsideration_trigger


def test_required_vnext_decision_fields_exist_for_every_market():
    for country, market in GLOBAL_MARKET_PORTFOLIO.items():
        assert market.country == country
        assert market.category
        assert market.commercial_score is not None
        assert market.technical_score is not None
        assert market.reuse_score is not None
        assert market.maintenance_score is not None
        assert market.strategic_role
        assert market.coverage_method
        assert market.connector_family is not None
        assert isinstance(market.dedicated_connector_required, bool)
        assert market.primary_blocker is not None
        assert market.reconsideration_trigger is not None
        assert market.decision_reason
