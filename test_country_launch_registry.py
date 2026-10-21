from country_launch_registry import (
    COUNTRY_LAUNCH_REGISTRY,
    first_wave,
    launch_market,
    upstream_pending_markets,
)
from global_market_portfolio import GLOBAL_MARKET_PORTFOLIO
from market_scope_registry import SHARED_FAMILIES


def test_launch_registry_covers_upstream_universe_without_redefining_it():
    assert set(COUNTRY_LAUNCH_REGISTRY) == set(GLOBAL_MARKET_PORTFOLIO)
    assert all(
        record.upstream_state == GLOBAL_MARKET_PORTFOLIO[country].category
        for country, record in COUNTRY_LAUNCH_REGISTRY.items()
    )


def test_first_wave_is_research_not_launch_authorization():
    assert first_wave() == ("Portugal", "Spain", "United Kingdom", "France", "Italy")
    assert all(launch_market(country).launch_state == "LAUNCH_RESEARCH" for country in first_wave())
    assert all(launch_market(country).priority == "LAUNCH_NOW" for country in first_wave())


def test_blocked_build_markets_fail_closed():
    assert launch_market("Brazil").launch_state == "UPSTREAM_PENDING"
    assert "stable live PNCP" in launch_market("Brazil").blocker
    assert launch_market("Chile").launch_state == "UPSTREAM_PENDING"
    assert "machine_access_not_verified" in launch_market("Chile").blocker
    assert {"Brazil", "Chile"}.issubset(set(upstream_pending_markets()))


def test_us_and_canada_never_claim_national_completeness():
    assert "SLED coverage is not implied" in launch_market("United States").product_coverage
    assert "provincial/municipal coverage is not implied" in launch_market("Canada").product_coverage


def test_ted_shared_markets_never_claim_national_below_threshold_completeness():
    for country in SHARED_FAMILIES["TED_EFORMS"]:
        record = launch_market(country)
        assert record.upstream_state == "SHARED"
        assert "national/below-threshold coverage is not implied" in record.product_coverage


def test_shared_markets_without_current_explicit_binding_are_not_faked_green():
    for country in ("Dominican Republic", "Guatemala", "Honduras", "Peru"):
        record = launch_market(country)
        assert record.upstream_state == "SHARED"
        assert record.launch_state == "UPSTREAM_PENDING"
        assert record.source_bindings == ()
        assert "no explicit launch-safe source binding" in record.blocker


def test_non_active_upstream_states_cannot_enter_launch_research():
    for record in COUNTRY_LAUNCH_REGISTRY.values():
        if record.upstream_state not in {"BUILD", "SHARED"}:
            assert record.launch_state != "LAUNCH_RESEARCH"
