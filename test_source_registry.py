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


def test_ready_source_is_not_legacy_active_by_registry_entry_alone():
    assert SOURCES["SERVICE_BUND_DE"]["status"] == "ready"
    assert "SERVICE_BUND_DE" not in active_sources()


def test_active_sources_have_access_metadata():
    for meta in active_sources().values():
        assert meta["kind"]
        assert meta["access"]
        assert meta["country"]
        assert meta["source_id"]
        assert meta["stale_after_minutes"] > 0


def test_wave_1_keeps_canonical_count_without_faking_planned_machine_gates():
    wave_1 = wave_sources(1)
    ready = {name: meta for name, meta in wave_1.items() if meta["status"] == "ready"}
    assert len(wave_1) == 15
    assert "CA_CANADABUYS" not in wave_1
    assert all(meta["official"] for meta in wave_1.values())
    assert all(meta["legal_reuse"] == "GREEN" for meta in wave_1.values())
    assert {meta["status"] for meta in wave_1.values()} <= {"planned", "ready"}
    assert len(ready) == 14
    assert all(meta["machine_access"] == "VERIFIED" for meta in ready.values())
    assert SOURCES["KR_KONEPS"]["status"] == "planned"
    assert SOURCES["KR_KONEPS"]["machine_access"] == "CREDENTIAL_REQUIRED"


def test_live_validated_ready_sources_pass_registry_gate():
    for source in (
        "CA_CANADABUYS",
        "CH_SIMAP",
        "CO_SECOP",
        "EC_SERCOP",
        "PY_DNCP",
        "UY_ARCE",
        "ZA_ETENDERS",
        "LV_IUB",
        "UK_PROCUREMENT",
        "PL_BZP",
        "EE_RHR",
        "AT_KERNDATEN",
        "LT_VPT",
        "NL_TENDERNED",
        "IT_ANAC",
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
    assert source["adapter"] == "OCDSMonthlyBulkConnector"
    assert source["signal_types"] == ("TENDER",)
    assert set(source["capabilities"]) == {"incremental_sync", "detail"}
    assert source["realtime_capable"] is False
    assert source["expected_refresh_minutes"] == 1440
    assert source["stale_after_minutes"] == 4320
    assert "search" not in source["capabilities"]
    assert "awards" not in source["capabilities"]
    assert "contracts" not in source["capabilities"]
    assert "plans" not in source["capabilities"]


def test_arce_registry_describes_rss_cursor_plus_pac_snapshot_architecture():
    source = SOURCES["UY_ARCE"]
    assert source["kind"] == "OCDS_RSS_RECORD_API"
    assert source["access"] == "rss_record_release_api_and_pac_snapshot"
    assert source["adapter"] == "ARCEOCDSRSSAdapter+ARCEPACConnector"
    assert source["signal_types"] == ("PROCUREMENT_PLAN", "TENDER")
    assert source["realtime_capable"] is True
    assert {"incremental_sync", "detail", "historical_data", "amendments", "plans"} <= set(source["capabilities"])


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


def test_simap_registry_declares_only_proven_public_tender_contract():
    source = SOURCES["CH_SIMAP"]
    assert source["kind"] == "PUBLIC_PROCUREMENT_API"
    assert source["access"] == "public_project_search_api"
    assert source["adapter"] == "SIMAPConnector"
    assert source["signal_types"] == ("TENDER",)
    assert set(source["capabilities"]) == {"search", "incremental_sync", "detail", "lots"}
    assert source["realtime_capable"] is True
    assert source["expected_refresh_minutes"] == 60
    assert source["stale_after_minutes"] == 180
    assert "awards" not in source["capabilities"]
    assert "contracts" not in source["capabilities"]
    assert "historical_data" not in source["capabilities"]


def test_poland_registry_declares_only_proven_bzp_tender_contract():
    source = SOURCES["PL_BZP"]
    assert source["kind"] == "PUBLIC_PROCUREMENT_API"
    assert source["access"] == "public_read_webservice"
    assert source["adapter"] == "PolandBZPConnector"
    assert source["signal_types"] == ("TENDER",)
    assert set(source["capabilities"]) == {"incremental_sync", "detail", "amendments", "lifecycle"}
    assert source["realtime_capable"] is True
    assert source["expected_refresh_minutes"] == 60
    assert source["stale_after_minutes"] == 180
    assert "plans" not in source["capabilities"]
    assert "awards" not in source["capabilities"]
    assert "contracts" not in source["capabilities"]


def test_estonia_registry_declares_only_proven_monthly_tender_lifecycle_contract():
    source = SOURCES["EE_RHR"]
    assert source["kind"] == "OFFICIAL_XML_EFORMS_BULK"
    assert source["access"] == "public_monthly_xml"
    assert source["adapter"] == "EstoniaRHRConnector"
    assert source["signal_types"] == ("TENDER",)
    assert set(source["capabilities"]) == {"incremental_sync", "lots", "lifecycle"}
    assert source["realtime_capable"] is False
    assert source["expected_refresh_minutes"] == 1440
    assert source["stale_after_minutes"] == 4320
    assert "search" not in source["capabilities"]
    assert "awards" not in source["capabilities"]
    assert "contracts" not in source["capabilities"]
    assert "historical_data" not in source["capabilities"]


def test_austria_registry_declares_only_proven_distributed_tender_contract():
    source = SOURCES["AT_KERNDATEN"]
    assert source["kind"] == "OFFICIAL_DISTRIBUTED_XML"
    assert source["access"] == "public_catalogue_kdq_xml"
    assert source["adapter"] == "AustriaKerndatenIncrementalConnector"
    assert source["signal_types"] == ("TENDER",)
    assert set(source["capabilities"]) == {"incremental_sync", "detail", "lifecycle"}
    assert source["realtime_capable"] is False
    assert source["expected_refresh_minutes"] == 720
    assert source["stale_after_minutes"] == 2160


def test_staleness_is_source_specific():
    assert stale_after_minutes_for("PY_DNCP") == 180
    assert stale_after_minutes_for("UNKNOWN", 77) == 77


def test_chile_mercadopublico_is_prebuilt_but_credential_gated():
    source = SOURCES["CL_MERCADOPUBLICO"]
    assert source["status"] == "planned"
    assert source["machine_access"] == "CREDENTIAL_REQUIRED"
    assert source["access"] == "personal_ticket_required"
    assert source["adapter"] == "MercadoPublicoConnector"
    assert set(source["capabilities"]) == {"incremental_sync", "detail", "lifecycle"}
    assert "CL_MERCADOPUBLICO" not in production_ready_sources()
    assert set(production_gate_reasons("CL_MERCADOPUBLICO")) == {
        "machine_access_not_verified", "runtime_not_enabled"
    }
