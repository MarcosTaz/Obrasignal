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
    assert sum(meta["status"] == "ready" for meta in wave_1.values()) == 7


def test_live_validated_wave_1_sources_pass_registry_gate():
    for source in (
        "CO_SECOP",
        "EC_SERCOP",
        "PY_DNCP",
        "UY_ARCE",
        "ZA_ETENDERS",
        "LV_IUB",
        "UK_PROCUREMENT",
    ):
        assert SOURCES[source]["status"] == "ready"
        assert production_gate_reasons(source) == ()
        assert source in production_ready_sources()


def test_dncp_registry_declares_oauth_and_realtime_capability():
    assert SOURCES["PY_DNCP"]["access"] == "api_oauth"
    assert SOURCES["PY_DNCP"]["adapter"] == "OCDSAPIConnector"
    assert SOURCES["PY_DNCP"]["realtime_capable"] is True


def test_ecuador_registry_declares_only_proven_bulk_record_tender_contract():
    source = SOURCES["EC_SERCOP"]
    assert source["kind"] == "OCDS_MONTHLY_BULK_RECORD_API"
    assert source["access"] == "public_monthly_bulk_record_api"
    assert source["adapter"] == "SERCOPBulkRecordConnector"
    assert source["signal_types"] == ("TENDER",)
    assert set(source["capabilities"]) == {"incremental_sync", "detail"}
    assert source["realtime_capable"] is False
    assert source["expected_refresh_minutes"] == 1440
    assert source["stale_after_minutes"] == 4320
    assert "search" not in source["capabilities"]
    assert "awards" not in source["capabilities"]
    assert "contracts" not in source["capabilities"]
    assert "plans" not in source["capabilities"]


def test_arce_registry_describes_actual_rss_record_release_architecture():
    source = SOURCES["UY_ARCE"]
    assert source["kind"] == "OCDS_RSS_RECORD_API"
    assert source["access"] == "rss_record_release_api"
    assert source["adapter"] == "ARCEOCDSRSSAdapter"
    assert source["signal_types"] == ("TENDER",)
    assert source["realtime_capable"] is True
    assert {"incremental_sync", "detail", "historical_data", "amendments"} <= set(source["capabilities"])


def test_za_registry_declares_only_implemented_tender_api_contract():
    source = SOURCES["ZA_ETENDERS"]
    assert source["kind"] == "OCDS_RELEASE_API"
    assert source["access"] == "public_date_window_api"
    assert source["adapter"] == "OCDSAPIConnector"
    assert source["signal_types"] == ("TENDER",)
    assert {"search", "incremental_sync", "historical_data"} <= set(source["capabilities"])
    assert "awards" not in source["capabilities"]


def test_lv_registry_declares_only_implemented_daily_tender_contract():
    source = SOURCES["LV_IUB"]
    assert source["kind"] == "OFFICIAL_JSON_BULK"
    assert source["access"] == "daily_json"
    assert source["adapter"] == "OfficialJSONBulkAdapter"
    assert source["signal_types"] == ("TENDER",)
    assert set(source["capabilities"]) == {"incremental_sync", "historical_data"}
    assert "awards" not in source["capabilities"]


def test_uk_registry_declares_only_proven_release_record_tender_contract():
    source = SOURCES["UK_PROCUREMENT"]
    assert source["kind"] == "OCDS_RELEASE_RECORD_API"
    assert source["access"] == "public_release_record_api"
    assert source["adapter"] == "UKFindTenderConnector"
    assert source["signal_types"] == ("TENDER",)
    assert set(source["capabilities"]) == {"search", "incremental_sync", "detail", "lots"}
    assert source["realtime_capable"] is True
    assert "awards" not in source["capabilities"]
    assert "contracts" not in source["capabilities"]
    assert "historical_data" not in source["capabilities"]


def test_germany_does_not_pass_production_gate_until_legal_closure():
    reasons = production_gate_reasons("SERVICE_BUND_DE")
    assert "commercial_reuse_not_green" in reasons
    assert "runtime_not_enabled" in reasons
    assert "SERVICE_BUND_DE" not in production_ready_sources()


def test_planned_wave_source_does_not_become_runtime_active_by_registry_entry_alone():
    reasons = production_gate_reasons("KR_KONEPS")
    assert reasons == ("runtime_not_enabled",)
    assert "KR_KONEPS" not in production_ready_sources()


def test_registered_source_freshness_is_source_specific():
    assert stale_after_minutes_for("TED") == 60
    assert stale_after_minutes_for("PY_DNCP") == 180
    assert stale_after_minutes_for("UY_ARCE") == 180
    assert stale_after_minutes_for("UK_PROCUREMENT") == 180
    assert stale_after_minutes_for("EC_SERCOP") == 4320
    assert stale_after_minutes_for("ZA_ETENDERS") == 4320
    assert stale_after_minutes_for("LV_IUB") == 4320
    assert stale_after_minutes_for("EE_RHR") == 64800
    assert stale_after_minutes_for("UNKNOWN_SOURCE", default=17) == 17
