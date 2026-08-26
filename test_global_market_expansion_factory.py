from global_market_expansion_factory import (
    COUNTRY_OPERATIONAL_STATE,
    DISCOVERY_CANDIDATES,
    HOLD_MONITORS,
    LEGAL_EVIDENCE,
    PRIORITY_A,
    SHARED_COVERAGE_AUDIT,
    active_proven_eligible,
    dashboard_counts,
)
from global_market_portfolio import GLOBAL_MARKET_PORTFOLIO, portfolio_counts


def test_factory_reconciles_current_portfolio_not_historical_counts():
    assert len(GLOBAL_MARKET_PORTFOLIO) == 135
    assert portfolio_counts() == {
        "BUILD": 14,
        "SHARED": 31,
        "TECH_LAB": 3,
        "HOLD": 26,
        "REMOVE": 61,
    }


def test_operational_registry_covers_canonical_universe_exactly_once():
    assert set(COUNTRY_OPERATIONAL_STATE) == set(GLOBAL_MARKET_PORTFOLIO)
    assert len(COUNTRY_OPERATIONAL_STATE) == 135


def test_priority_a_is_fail_closed_and_independent():
    assert PRIORITY_A["Brazil"].classification == "PARTIAL_CONNECTOR"
    assert PRIORITY_A["Brazil"].legal_state == "LEGAL_AMBER"
    assert COUNTRY_OPERATIONAL_STATE["Brazil"] == "TECHNICAL_BLOCKED"

    assert PRIORITY_A["Canada"].classification == "INTEGRATION_PENDING"
    assert PRIORITY_A["United States"].classification == "INTEGRATION_PENDING"
    assert COUNTRY_OPERATIONAL_STATE["Canada"] == "INTEGRATION_PENDING"
    assert COUNTRY_OPERATIONAL_STATE["United States"] == "INTEGRATION_PENDING"

    assert PRIORITY_A["Chile"].classification == "LIVE_CONTRACT_UNKNOWN"
    assert COUNTRY_OPERATIONAL_STATE["Chile"] == "TECHNICAL_BLOCKED"


def test_fresh_priority_a_legal_evidence_does_not_infer_brazil_green():
    assert LEGAL_EVIDENCE["Canada"].classification == "LEGAL_GREEN"
    assert LEGAL_EVIDENCE["United States"].classification == "LEGAL_GREEN"
    assert LEGAL_EVIDENCE["Chile"].classification == "LEGAL_GREEN"
    assert LEGAL_EVIDENCE["Brazil"].classification == "LEGAL_AMBER"
    assert LEGAL_EVIDENCE["Brazil"].redistribution == "UNKNOWN"
    assert LEGAL_EVIDENCE["Brazil"].derivative_use == "UNKNOWN"


def test_all_31_shared_markets_are_individually_audited():
    assert len(SHARED_COVERAGE_AUDIT) == 31
    assert all(row.country == country for country, row in SHARED_COVERAGE_AUDIT.items())
    assert not any(row.operational_state == "ACTIVE_PROVEN" for row in SHARED_COVERAGE_AUDIT.values())


def test_shared_problem_markets_preserve_their_exact_gate():
    assert SHARED_COVERAGE_AUDIT["Peru"].operational_state == "TECHNICAL_BLOCKED"
    assert SHARED_COVERAGE_AUDIT["Guatemala"].operational_state == "TECHNICAL_BLOCKED"
    assert SHARED_COVERAGE_AUDIT["Honduras"].operational_state == "TECHNICAL_BLOCKED"
    assert SHARED_COVERAGE_AUDIT["Dominican Republic"].operational_state == "INTEGRATION_PENDING"


def test_current_vnext_hold_markets_all_have_monitors():
    current_hold = {
        country for country, market in GLOBAL_MARKET_PORTFOLIO.items()
        if market.category == "HOLD"
    }
    assert set(HOLD_MONITORS) == current_hold
    assert len(HOLD_MONITORS) == 26
    for monitor in HOLD_MONITORS.values():
        assert monitor.reopen_trigger
        assert monitor.monitor_query
        assert monitor.official_authorities
        assert monitor.last_checked == "2026-08-26"
        assert monitor.next_check
        assert monitor.monitoring_method


def test_vnext_tech_lab_markets_are_not_falsely_kept_in_hold_monitor_count():
    for country in ("Uganda", "Tanzania", "Zambia"):
        assert GLOBAL_MARKET_PORTFOLIO[country].category == "TECH_LAB"
        assert country not in HOLD_MONITORS
        assert COUNTRY_OPERATIONAL_STATE[country] == "RESEARCHING"
    assert GLOBAL_MARKET_PORTFOLIO["Namibia"].category == "HOLD"
    assert "Namibia" in HOLD_MONITORS


def test_known_hold_reopen_queries_are_narrow_not_full_research_loops():
    assert "KONEPS_SERVICE_KEY" in HOLD_MONITORS["South Korea"].monitor_query
    assert "licence" in HOLD_MONITORS["Rwanda"].monitor_query
    assert "API/feed" in HOLD_MONITORS["India"].monitor_query
    assert "AusTender" in HOLD_MONITORS["Australia"].monitor_query
    assert "ComprasMX" in HOLD_MONITORS["Mexico"].monitor_query


def test_discovery_registry_extends_beyond_135_without_promoting_candidates():
    assert set(DISCOVERY_CANDIDATES).isdisjoint(GLOBAL_MARKET_PORTFOLIO)
    assert len(DISCOVERY_CANDIDATES) == 8
    assert DISCOVERY_CANDIDATES["Turkey"].state == "RESEARCHING"
    assert DISCOVERY_CANDIDATES["Serbia"].state == "RESEARCHING"
    assert all(item.state in {"DISCOVERED", "RESEARCHING"} for item in DISCOVERY_CANDIDATES.values())


def test_dashboard_counts_are_exact_counts_not_percentages():
    counts = dashboard_counts()
    assert counts["TOTAL_JURISDICTIONS_DISCOVERED"] == 143
    assert counts["CANONICAL_PORTFOLIO_JURISDICTIONS"] == 135
    assert counts["BUILD"] == 14
    assert counts["SHARED"] == 31
    assert counts["HOLD"] == 26
    assert counts["REMOVE"] == 61
    assert counts["DISCOVERED_OUTSIDE_CANONICAL"] == 8
    assert counts["ACTIVE_PROVEN"] == 0


def test_active_proven_requires_every_gate():
    gates = dict(
        legal_green=True,
        technical_source_green=True,
        identity_green=True,
        pagination_green=True,
        restart_green=True,
        lifecycle_green=True,
        temporal_green=True,
        normalization_green=True,
        tenant_safe_green=True,
        source_health_green=True,
        provenance_green=True,
        integration_green=True,
        golden_green=True,
    )
    assert active_proven_eligible(**gates) is True
    for gate in gates:
        variant = dict(gates)
        variant[gate] = False
        assert active_proven_eligible(**variant) is False, gate
