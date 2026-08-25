from source_registry import SOURCES, active_sources, production_ready_sources


def test_registered_source_is_not_equivalent_to_active_market_coverage():
    registered = set(SOURCES)
    active = set(active_sources())
    ready = set(production_ready_sources())

    assert active <= registered
    assert ready <= registered
    assert registered - active, "Registry must preserve planned/ready/opt-in sources without pretending they are active"


def test_ready_source_is_not_equivalent_to_running_ingestion():
    ready_not_active = set(production_ready_sources()) - set(active_sources())
    assert ready_not_active, "A production-ready source must remain distinguishable from an active runtime source"


def test_portugal_active_sources_do_not_prove_full_national_market_completeness():
    portugal_active = {
        name
        for name, meta in active_sources().items()
        if meta.get("country") in {"PRT", "EU"}
    }
    assert portugal_active

    # Source presence proves only observed coverage from those source contracts.
    # There is intentionally no registry field asserting national/full-market completeness.
    for name in portugal_active:
        meta = SOURCES[name]
        assert "national_market_complete" not in meta
        assert "full_market_coverage" not in meta
        assert "all_procurement" not in meta


def test_source_capability_scope_cannot_be_silently_widened_to_market_completeness():
    for name, meta in SOURCES.items():
        capabilities = set(meta.get("capabilities") or ())
        assert "full_market_coverage" not in capabilities, name
        assert "national_completeness" not in capabilities, name
        assert "all_procurement" not in capabilities, name
