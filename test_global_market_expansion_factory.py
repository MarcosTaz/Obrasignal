import global_market_expansion_factory as factory
from global_market_expansion_factory import (
    COUNTRY_OPERATIONAL_STATE,
    DISCOVERY_CANDIDATES,
    HOLD_MONITORS,
    LEGAL_EVIDENCE,
    OWNER_ROUTING_DEFECTS,
    PRIORITY_A,
    SHARED_COVERAGE_AUDIT,
    active_proven_eligible,
    dashboard_counts,
    legal_change_watch_targets,
)
from global_market_portfolio import GLOBAL_MARKET_PORTFOLIO, portfolio_counts
from global_market_source_contracts import SOURCE_CONTRACTS


def test_factory_reconciles_current_vnext_portfolio_not_legacy_counts():
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


def test_priority_a_separates_canonical_code_candidate_code_and_promotion_state():
    assert PRIORITY_A["Brazil"].classification == "PARTIAL_CONNECTOR"
    assert PRIORITY_A["Brazil"].canonical_code == "UNKNOWN"
    assert PRIORITY_A["Brazil"].candidate_code == "PROVEN"
    assert PRIORITY_A["Brazil"].legal_state == "LEGAL_AMBER"
    assert COUNTRY_OPERATIONAL_STATE["Brazil"] == "TECHNICAL_BLOCKED"

    assert PRIORITY_A["Canada"].classification == "CONNECTOR_GREEN"
    assert COUNTRY_OPERATIONAL_STATE["Canada"] == "INTEGRATION_PENDING"

    assert PRIORITY_A["United States"].classification == "CONNECTOR_GREEN"
    assert PRIORITY_A["United States"].legal_state == "LEGAL_AMBER"
    assert COUNTRY_OPERATIONAL_STATE["United States"] == "LEGAL_UNKNOWN"

    assert PRIORITY_A["Chile"].classification == "LIVE_CONTRACT_UNKNOWN"
    assert COUNTRY_OPERATIONAL_STATE["Chile"] == "TECHNICAL_BLOCKED"


def test_fresh_legal_evidence_never_infers_unknown_commercial_rights_green():
    assert LEGAL_EVIDENCE["Canada"].classification == "LEGAL_GREEN"
    assert LEGAL_EVIDENCE["Chile"].classification == "LEGAL_GREEN"

    assert LEGAL_EVIDENCE["Brazil"].classification == "LEGAL_AMBER"
    assert LEGAL_EVIDENCE["Brazil"].redistribution == "UNKNOWN"
    assert LEGAL_EVIDENCE["Brazil"].derivative_use == "UNKNOWN"

    assert LEGAL_EVIDENCE["United States"].classification == "LEGAL_AMBER"
    assert LEGAL_EVIDENCE["United States"].commercial_reuse == "UNKNOWN"
    assert LEGAL_EVIDENCE["United States"].derivative_use == "UNKNOWN"

    assert all(
        evidence.fingerprint_scope == "CAPTURED_EVIDENCE_RECORD_NOT_REMOTE_PAGE_BYTES"
        for evidence in LEGAL_EVIDENCE.values()
    )


def test_priority_a_technical_contract_registry_is_single_separate_authority():
    assert set(SOURCE_CONTRACTS) == {"Brazil", "Canada", "United States", "Chile"}
    assert not hasattr(factory, "TECHNICAL_SOURCE_CONTRACTS")
    assert not hasattr(factory, "TechnicalSourceContract")
    assert SOURCE_CONTRACTS["Canada"].live_evidence == "PROVEN"
    assert SOURCE_CONTRACTS["United States"].live_evidence == "PROVEN"
    assert SOURCE_CONTRACTS["Chile"].live_evidence == "BLOCKED"
    assert SOURCE_CONTRACTS["Brazil"].live_evidence == "BLOCKED"


def test_us_source_registry_legal_drift_is_routed_not_silently_accepted():
    defect = OWNER_ROUTING_DEFECTS["US_SAM_LEGAL_DRIFT"]
    assert defect["issue"] == "#520"
    assert "LEGAL_AMBER" in defect["factory_evidence"]
    assert defect["invariant"] == "LEGAL_UNKNOWN/AMBER != LEGAL_GREEN"


def test_all_31_shared_markets_are_individually_audited_without_fake_active_proof():
    assert len(SHARED_COVERAGE_AUDIT) == 31
    assert all(row.country == country for country, row in SHARED_COVERAGE_AUDIT.items())
    assert not any(row.operational_state == "ACTIVE_PROVEN" for row in SHARED_COVERAGE_AUDIT.values())


def test_fresh_shared_publisher_legal_evidence_updates_only_legal_dimension():
    for country in ("Ecuador", "Paraguay", "South Africa"):
        row = SHARED_COVERAGE_AUDIT[country]
        assert row.legal_evidence == "PROVEN"
        assert row.operational_state == "INTEGRATION_PENDING"
    assert SHARED_COVERAGE_AUDIT["Uruguay"].legal_evidence == "PARTIAL"


def test_ted_family_health_is_not_23_country_golden_proof():
    ted_rows = [row for row in SHARED_COVERAGE_AUDIT.values() if row.family == "TED/eForms"]
    assert len(ted_rows) == 23
    assert all(row.source_family_eligibility == "PROVEN" for row in ted_rows)
    assert all(row.tests == "PARTIAL" for row in ted_rows)
    assert all(row.health_representation == "PARTIAL" for row in ted_rows)
    assert all(row.operational_state == "REVALIDATION_REQUIRED" for row in ted_rows)


def test_shared_problem_markets_preserve_exact_gate_and_uruguay_exception():
    assert SHARED_COVERAGE_AUDIT["Peru"].operational_state == "TECHNICAL_BLOCKED"
    assert SHARED_COVERAGE_AUDIT["Guatemala"].operational_state == "TECHNICAL_BLOCKED"
    assert SHARED_COVERAGE_AUDIT["Honduras"].operational_state == "TECHNICAL_BLOCKED"
    assert SHARED_COVERAGE_AUDIT["Dominican Republic"].operational_state == "INTEGRATION_PENDING"
    assert SHARED_COVERAGE_AUDIT["Uruguay"].source_family_eligibility == "PARTIAL"


def test_current_vnext_hold_markets_all_have_targeted_monitors():
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


def test_vnext_tech_lab_markets_are_not_falsely_counted_as_hold():
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


def test_discovery_registry_includes_existing_europe_and_mena_cells_without_promotion():
    assert set(DISCOVERY_CANDIDATES).isdisjoint(GLOBAL_MARKET_PORTFOLIO)
    assert len(DISCOVERY_CANDIDATES) == 13
    assert DISCOVERY_CANDIDATES["Turkey"].state == "RESEARCHING"
    assert DISCOVERY_CANDIDATES["Serbia"].state == "RESEARCHING"
    assert DISCOVERY_CANDIDATES["Qatar"].state == "LEGAL_BLOCKED"
    assert DISCOVERY_CANDIDATES["Bahrain"].state == "LEGAL_UNKNOWN"
    assert all(item.state != "ACTIVE_PROVEN" for item in DISCOVERY_CANDIDATES.values())


def test_dashboard_counts_are_exact_counts_not_percentages():
    counts = dashboard_counts()
    assert counts["TOTAL_JURISDICTIONS_DISCOVERED"] == 148
    assert counts["CANONICAL_PORTFOLIO_JURISDICTIONS"] == 135
    assert counts["DISCOVERED_OUTSIDE_CANONICAL"] == 13
    assert counts["BUILD"] == 14
    assert counts["SHARED"] == 31
    assert counts["TECH_LAB"] == 3
    assert counts["HOLD"] == 26
    assert counts["REMOVE"] == 61
    assert counts["ACTIVE_PROVEN"] == 0
    assert counts["INTEGRATION_PENDING"] == 13
    assert counts["REVALIDATION_REQUIRED"] == 26
    assert counts["TECHNICAL_BLOCKED"] == 5
    assert counts["LEGAL_UNKNOWN"] == 1
    assert counts["LEGAL_EVIDENCE_UNREVALIDATED"] == 131


def test_legal_change_watch_targets_real_urls_without_fake_remote_hashes():
    targets = legal_change_watch_targets()
    assert targets
    assert any(country == "Canada" and kind == "license" for country, kind, _, _ in targets)
    assert any(country == "United States" and kind == "terms" for country, kind, _, _ in targets)
    assert all(url.startswith("https://") for _, _, url, _ in targets)


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
