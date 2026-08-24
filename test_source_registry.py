from source_registry import (
    SOURCES,
    active_sources,
    production_gate_reasons,
    production_ready_sources,
    stale_after_minutes_for,
    wave_sources,
)


def test_verified_active_sources_are_official():
    active = active_sources()
    assert active
    assert all(meta["official"] for meta in active.values())


def test_research_source_is_not_marked_active():
    assert SOURCES["SERVICE_BUND_DE"]["status"] == "research"
    assert "SERVICE_BUND_DE" not in active_sources()


def test_active_sources_have_access_metadata():
    for meta in active_sources().values():
        assert meta["kind"]
        assert meta["access"]
        assert meta["country"]
        assert meta["source_id"]
        assert meta["stale_after_minutes"] > 0


def test_wave_1_contains_only_machine_verified_green_sources():
    wave_1 = wave_sources(1)
    assert len(wave_1) == 15
    assert all(meta["official"] for meta in wave_1.values())
    assert all(meta["machine_access"] == "VERIFIED" for meta in wave_1.values())
    assert all(meta["legal_reuse"] == "GREEN" for meta in wave_1.values())
    assert {meta["status"] for meta in wave_1.values()} <= {"planned", "ready"}
    assert sum(meta["status"] == "ready" for meta in wave_1.values()) == 3


def test_live_validated_wave_1_sources_pass_registry_gate():
    for source in ("CO_SECOP", "PY_DNCP", "UY_ARCE"):
        assert SOURCES[source]["status"] == "ready"
        assert production_gate_reasons(source) == ()
        assert source in production_ready_sources()


def test_dncp_registry_declares_oauth_and_realtime_capability():
    assert SOURCES["PY_DNCP"]["access"] == "api_oauth"
    assert SOURCES["PY_DNCP"]["adapter"] == "OCDSAPIConnector"
    assert SOURCES["PY_DNCP"]["realtime_capable"] is True


def test_arce_registry_describes_actual_rss_record_release_architecture():
    source = SOURCES["UY_ARCE"]
    assert source["kind"] == "OCDS_RSS_RECORD_API"
    assert source["access"] == "rss_record_release_api"
    assert source["adapter"] == "ARCEOCDSRSSAdapter"
    assert source["signal_types"] == ("TENDER",)
    assert source["realtime_capable"] is True
    assert {"incremental_sync", "detail", "historical_data", "amendments"} <= set(source["capabilities"])


def test_germany_does_not_pass_production_gate_until_legal_closure():
    reasons = production_gate_reasons("SERVICE_BUND_DE")
    assert "commercial_reuse_not_green" in reasons
    assert "runtime_not_enabled" in reasons
    assert "SERVICE_BUND_DE" not in production_ready_sources()


def test_planned_wave_source_does_not_become_runtime_active_by_registry_entry_alone():
    reasons = production_gate_reasons("EC_SERCOP")
    assert reasons == ("runtime_not_enabled",)
    assert "EC_SERCOP" not in production_ready_sources()


def test_registered_source_freshness_is_source_specific():
    assert stale_after_minutes_for("TED") == 60
    assert stale_after_minutes_for("PY_DNCP") == 180
    assert stale_after_minutes_for("UY_ARCE") == 180
    assert stale_after_minutes_for("LV_IUB") == 4320
    assert stale_after_minutes_for("EE_RHR") == 64800
    assert stale_after_minutes_for("UNKNOWN_SOURCE", default=17) == 17
