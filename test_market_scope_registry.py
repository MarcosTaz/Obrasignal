from market_scope_registry import (
    BUILD_ORDER,
    DEDICATED_CONNECTORS,
    DECISION_UNIVERSE,
    LEGACY_CONNECTOR_CANDIDATES,
    LEGACY_RESEARCH_MARKETS,
    MARKET_SCOPE,
    OFFICIAL_ACTIVE_MARKETS,
    SHARED_FAMILIES,
    TARGET_DEDICATED_CONNECTORS,
    active_markets,
    development_allowed,
    scope_counts,
)


def test_scope_partition_and_official_counts():
    assert LEGACY_RESEARCH_MARKETS == 108
    assert LEGACY_CONNECTOR_CANDIDATES == 45
    assert DECISION_UNIVERSE == 135
    assert scope_counts() == {
        "BUILD": 14,
        "SHARED": 31,
        "HOLD": 28,
        "REMOVE": 62,
    }
    assert len(MARKET_SCOPE) == DECISION_UNIVERSE
    assert len(active_markets()) == OFFICIAL_ACTIVE_MARKETS == 45


def test_country_specific_development_is_build_only():
    assert development_allowed("Brazil") is True
    assert development_allowed("Portugal") is True
    assert development_allowed("Austria") is False
    assert development_allowed("South Korea") is False
    assert development_allowed("Cabo Verde") is False


def test_shared_coverage_uses_only_common_families():
    shared = {
        country
        for countries in SHARED_FAMILIES.values()
        for country in countries
    }
    assert len(shared) == 31
    assert all(MARKET_SCOPE[country].status == "SHARED" for country in shared)
    assert all(MARKET_SCOPE[country].infrastructure for country in shared)


def test_connector_rebase_is_aggressive_and_explicit():
    assert len(DEDICATED_CONNECTORS) == TARGET_DEDICATED_CONNECTORS == 13
    assert set(DEDICATED_CONNECTORS).issubset(
        {country for country, decision in MARKET_SCOPE.items() if decision.status == "BUILD"}
    )
    # Colombia is BUILD through the shared Socrata adapter, not a new dedicated connector.
    assert MARKET_SCOPE["Colombia"].status == "BUILD"
    assert "Colombia" not in DEDICATED_CONNECTORS
    assert len(BUILD_ORDER) == 14


def test_hold_and_remove_cannot_silently_receive_development():
    for country, decision in MARKET_SCOPE.items():
        if decision.status == "HOLD":
            assert decision.reopen_condition
            assert not development_allowed(country)
        if decision.status == "REMOVE":
            assert decision.reason.startswith("Não justifica desenvolvimento porque")
            assert not development_allowed(country)
