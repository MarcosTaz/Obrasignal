"""Canonical procurement-source configuration for ObraSignal.

The runtime still supports the legacy short source names used by the current
European radar, but the registry now carries the production gates required by
the global architecture: legal reuse, machine-access verification, source
freshness, capabilities, signal types and implementation wave.

Adding a source to this file does *not* enable ingestion. A source is only
production-ready when its runtime status is active/ready and every gate passes.
"""


def _source(
    *,
    country,
    source_id,
    kind,
    access,
    status,
    priority,
    legal_reuse,
    machine_access,
    expected_refresh_minutes,
    stale_after_minutes,
    capabilities=(),
    signal_types=("TENDER",),
    wave=None,
    adapter=None,
    jurisdiction=None,
    realtime_capable=False,
):
    return {
        "country": country,
        "jurisdiction": jurisdiction or country,
        "source_id": source_id,
        "official": True,
        "kind": kind,
        "access": access,
        "status": status,
        "priority": priority,
        "legal_reuse": legal_reuse,
        "machine_access": machine_access,
        "expected_refresh_minutes": int(expected_refresh_minutes),
        "stale_after_minutes": int(stale_after_minutes),
        "capabilities": tuple(capabilities),
        "signal_types": tuple(signal_types),
        "wave": wave,
        "adapter": adapter,
        "realtime_capable": bool(realtime_capable),
    }


# Existing production radar + Wave-1 global source contracts. Planned sources
# remain disabled until their concrete connector and contract tests land.
SOURCES = {
    "TED": _source(
        country="EU",
        source_id="eu_ted_search_api",
        kind="EU_API",
        access="search_api",
        status="active",
        priority=1,
        legal_reuse="GREEN",
        machine_access="VERIFIED",
        expected_refresh_minutes=15,
        stale_after_minutes=60,
        capabilities=("search", "incremental_sync", "detail", "lots"),
        signal_types=("TENDER", "AWARD"),
        adapter="TEDSearchAdapter",
        realtime_capable=True,
    ),
    "BASE": _source(
        country="PRT",
        source_id="pt_base",
        kind="NATIONAL_PORTAL",
        access="existing_connector",
        status="active",
        priority=1,
        legal_reuse="GREEN",
        machine_access="VERIFIED",
        expected_refresh_minutes=1440,
        stale_after_minutes=2880,
        capabilities=("search", "detail", "contracts"),
        signal_types=("TENDER", "CONTRACT"),
        adapter="ExistingBaseConnector",
    ),
    "BOAMP": _source(
        country="FRA",
        source_id="fr_boamp_open_data",
        kind="OPEN_DATA_API",
        access="api",
        status="active",
        priority=1,
        legal_reuse="GREEN",
        machine_access="VERIFIED",
        expected_refresh_minutes=60,
        stale_after_minutes=180,
        capabilities=("search", "incremental_sync"),
        adapter="BOAMPAdapter",
        realtime_capable=True,
    ),
    "PLACSP": _source(
        country="ESP",
        source_id="es_placsp_atom",
        kind="ATOM_FEED",
        access="feed",
        status="active",
        priority=1,
        legal_reuse="GREEN",
        machine_access="VERIFIED",
        expected_refresh_minutes=60,
        stale_after_minutes=180,
        capabilities=("search", "incremental_sync", "detail"),
        adapter="PLACSPAtomAdapter",
        realtime_capable=True,
    ),
    "PMP-LU": _source(
        country="LUX",
        source_id="lu_marches_publics",
        kind="RSS",
        access="environment_configured",
        status="opt_in",
        priority=2,
        legal_reuse="YELLOW",
        machine_access="VERIFIED",
        expected_refresh_minutes=60,
        stale_after_minutes=180,
        capabilities=("search", "incremental_sync"),
        adapter="OfficialRSSAdapter",
        realtime_capable=True,
    ),
    "SERVICE_BUND_DE": _source(
        country="DEU",
        source_id="de_doe_bekanntmachungsservice",
        kind="OFFICIAL_EFORMS_DAILY_BULK",
        access="public_daily_eforms_zip",
        status="ready",
        priority=2,
        legal_reuse="GREEN",
        machine_access="VERIFIED",
        expected_refresh_minutes=1440,
        stale_after_minutes=4320,
        capabilities=("incremental_sync", "lots", "lifecycle"),
        signal_types=("TENDER",),
        adapter="GermanDOEOpenDataConnector",
        realtime_capable=False,
    ),
    "EC_SERCOP": _source(
        country="ECU",
        source_id="ec_sercop_ocds",
        kind="OCDS_MONTHLY_BULK_RECORD_API",
        access="public_monthly_bulk_record_api",
        status="ready",
        priority=1,
        legal_reuse="GREEN",
        machine_access="VERIFIED",
        expected_refresh_minutes=1440,
        stale_after_minutes=4320,
        capabilities=("incremental_sync", "detail"),
        signal_types=("TENDER",),
        wave=1,
        adapter="OCDSMonthlyBulkConnector",
        realtime_capable=False,
    ),
    "PY_DNCP": _source(country="PRY", source_id="py_dncp_api_v3", kind="OCDS_API", access="api_oauth", status="ready", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=60, stale_after_minutes=180, capabilities=("search", "incremental_sync", "awards", "contracts", "plans", "amendments"), signal_types=("PROCUREMENT_PLAN", "TENDER", "AWARD", "CONTRACT"), wave=1, adapter="OCDSAPIConnector", realtime_capable=True),
    "KR_KONEPS": _source(country="KOR", source_id="kr_koneps_bid_notice_api", kind="OFFICIAL_CONSTRUCTION_BID_NOTICE_API", access="portal_service_key_required", status="planned", priority=1, legal_reuse="GREEN", machine_access="CREDENTIAL_REQUIRED", expected_refresh_minutes=15, stale_after_minutes=60, capabilities=(), signal_types=("TENDER",), wave=1, adapter=None, realtime_capable=True),
    "CH_SIMAP": _source(country="CHE", source_id="ch_simap_api", kind="PUBLIC_PROCUREMENT_API", access="public_project_search_api", status="ready", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=60, stale_after_minutes=180, capabilities=("search", "incremental_sync", "detail", "lots"), signal_types=("TENDER",), wave=1, adapter="SIMAPConnector", realtime_capable=True),
    "IT_ANAC": _source(country="ITA", source_id="it_anac_bdncp_pvl", kind="OFFICIAL_PUBLIC_LEGAL_NOTICE_API", access="public_json_day_window", status="ready", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=60, stale_after_minutes=180, capabilities=("incremental_sync", "lots", "lifecycle"), signal_types=("TENDER",), wave=1, adapter="ANACPVLConnector", realtime_capable=True),
    "UY_ARCE": _source(country="URY", source_id="uy_arce_ocds", kind="OCDS_RSS_RECORD_API", access="rss_record_release_api", status="ready", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=60, stale_after_minutes=180, capabilities=("incremental_sync", "detail", "historical_data", "amendments"), signal_types=("TENDER",), wave=1, adapter="ARCEOCDSRSSAdapter", realtime_capable=True),
    "UK_PROCUREMENT": _source(
        country="GBR",
        source_id="uk_find_a_tender_contracts_finder",
        kind="OCDS_RELEASE_RECORD_API",
        access="public_release_record_api",
        status="ready",
        priority=1,
        legal_reuse="GREEN",
        machine_access="VERIFIED",
        expected_refresh_minutes=60,
        stale_after_minutes=180,
        capabilities=("search", "incremental_sync", "detail", "lots"),
        signal_types=("TENDER",),
        wave=1,
        adapter="UKFindTenderConnector",
        realtime_capable=True,
    ),
    "LV_IUB": _source(country="LVA", source_id="lv_iub_open_data", kind="OFFICIAL_JSON_BULK", access="daily_json", status="ready", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=1440, stale_after_minutes=4320, capabilities=("incremental_sync", "historical_data"), signal_types=("TENDER",), wave=1, adapter="OfficialJSONBulkAdapter"),
    "ZA_ETENDERS": _source(country="ZAF", source_id="za_etenders_ocds", kind="OCDS_RELEASE_API", access="public_date_window_api", status="ready", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=1440, stale_after_minutes=4320, capabilities=("search", "incremental_sync", "historical_data"), signal_types=("TENDER",), wave=1, adapter="OCDSAPIConnector"),
    "PL_BZP": _source(country="POL", source_id="pl_ezamowienia_bzp_webservice", kind="PUBLIC_PROCUREMENT_API", access="public_read_webservice", status="ready", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=60, stale_after_minutes=180, capabilities=("incremental_sync", "detail", "amendments", "lifecycle"), signal_types=("TENDER",), wave=1, adapter="PolandBZPConnector", realtime_capable=True),
    "AT_KERNDATEN": _source(country="AUT", source_id="at_bvergg_kerndaten", kind="OFFICIAL_DISTRIBUTED_XML", access="public_catalogue_kdq_xml", status="ready", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=720, stale_after_minutes=2160, capabilities=("incremental_sync", "detail", "lifecycle"), signal_types=("TENDER",), wave=1, adapter="AustriaKerndatenIncrementalConnector", realtime_capable=False),
    "NL_TENDERNED": _source(country="NLD", source_id="nl_tenderned", kind="PUBLIC_LIST_DETAIL_API", access="public_json_list_detail", status="ready", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=60, stale_after_minutes=180, capabilities=("incremental_sync", "detail", "amendments", "lifecycle"), signal_types=("TENDER",), wave=1, adapter="TenderNedPublicConnector", realtime_capable=True),
    "LT_VPT": _source(country="LTU", source_id="lt_vpt_cvp_is", kind="OFFICIAL_PUBLIC_SNAPSHOT_API", access="public_shared_api_key_snapshot", status="ready", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=1440, stale_after_minutes=4320, capabilities=("incremental_sync", "lifecycle"), signal_types=("TENDER",), wave=1, adapter="LithuaniaVPTSnapshotConnector", realtime_capable=False),
    "EE_RHR": _source(country="EST", source_id="ee_rhr_public_api", kind="OFFICIAL_XML_EFORMS_BULK", access="public_monthly_xml", status="ready", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=1440, stale_after_minutes=4320, capabilities=("incremental_sync", "lots", "lifecycle"), signal_types=("TENDER",), wave=1, adapter="EstoniaRHRConnector", realtime_capable=False),
    "CO_SECOP": _source(country="COL", source_id="co_secop_open_data", kind="SOCRATA_ODATA", access="api", status="ready", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=1440, stale_after_minutes=4320, capabilities=("search", "incremental_sync", "awards", "contracts", "plans", "suppliers"), signal_types=("PROCUREMENT_PLAN", "TENDER", "AWARD", "CONTRACT"), wave=1, adapter="SocrataProcurementAdapter"),
    "CL_MERCADOPUBLICO": _source(
        country="CHL",
        source_id="cl_mercadopublico_licitaciones_api",
        kind="OFFICIAL_PUBLIC_PROCUREMENT_API",
        access="personal_ticket_required",
        status="planned",
        priority=1,
        legal_reuse="GREEN",
        machine_access="CREDENTIAL_REQUIRED",
        expected_refresh_minutes=60,
        stale_after_minutes=180,
        capabilities=("incremental_sync", "detail", "lifecycle"),
        signal_types=("TENDER",),
        adapter="MercadoPublicoConnector",
        realtime_capable=True,
    ),
    "US_SAM": _source(
        country="USA",
        source_id="us_sam_contract_opportunities",
        kind="OFFICIAL_PUBLIC_DAILY_CSV_SNAPSHOT",
        access="public_contract_opportunities_full_csv",
        status="ready",
        priority=1,
        legal_reuse="GREEN",
        machine_access="VERIFIED",
        expected_refresh_minutes=1440,
        stale_after_minutes=4320,
        capabilities=("incremental_sync", "contacts", "set_asides"),
        signal_types=("TENDER",),
        adapter="SAMGovConnector",
        realtime_capable=False,
    ),
    "CA_CANADABUYS": _source(
        country="CAN",
        source_id="ca_canadabuys_tender_notices",
        kind="OFFICIAL_PUBLIC_CSV_DELTA_SNAPSHOT",
        access="public_new_open_complete_csv",
        status="ready",
        priority=1,
        legal_reuse="GREEN",
        machine_access="VERIFIED",
        expected_refresh_minutes=120,
        stale_after_minutes=2880,
        capabilities=("incremental_sync", "amendments", "lifecycle"),
        signal_types=("TENDER",),
        adapter="CanadaBuysConnector",
        realtime_capable=False,
    ),
    "QA_ASHGHAL": _source(
        country="QAT",
        jurisdiction="Qatar / Public Works Authority (Ashghal)",
        source_id="qa_ashghal_open_etenders",
        kind="OFFICIAL_PUBLIC_HTML_LIST",
        access="public_open_etenders_html",
        status="planned",
        priority=1,
        legal_reuse="YELLOW",
        machine_access="VERIFIED",
        expected_refresh_minutes=1440,
        stale_after_minutes=4320,
        capabilities=("search", "construction_filter"),
        signal_types=("TENDER",),
        adapter="AshghalOpenTenderConnector",
        realtime_capable=False,
    ),
    "IL_GPA": _source(
        country="ISR",
        jurisdiction="Israel / Government Procurement Administration public search",
        source_id="il_gpa_mr_public_procurement",
        kind="OFFICIAL_PUBLIC_HTML_SEARCH_DETAIL",
        access="public_search_detail_html",
        status="planned",
        priority=2,
        legal_reuse="YELLOW",
        machine_access="VERIFIED",
        expected_refresh_minutes=1440,
        stale_after_minutes=4320,
        capabilities=("search", "detail", "construction_filter"),
        signal_types=("TENDER",),
        adapter="IsraelGPAConnector",
        realtime_capable=False,
    ),
    "OM_ESNAD": _source(
        country="OMN",
        jurisdiction="Oman / Tender Board Esnad Upcoming Tender",
        source_id="om_esnad_public_procurement",
        kind="OFFICIAL_PUBLIC_HTML_PROCUREMENT_PLAN",
        access="public_upcoming_tenders_html",
        status="planned",
        priority=1,
        legal_reuse="YELLOW",
        machine_access="VERIFIED",
        expected_refresh_minutes=1440,
        stale_after_minutes=4320,
        capabilities=("search", "plans", "construction_filter"),
        signal_types=("PROCUREMENT_PLAN",),
        adapter="OmanEsnadUpcomingConnector",
        realtime_capable=False,
    ),
    "AE_MOF_DPP": _source(
        country="ARE",
        jurisdiction="UAE federal / Ministry of Finance business opportunities",
        source_id="ae_mof_dpp_public_business_opportunities",
        kind="OFFICIAL_PUBLIC_HTML_LIST",
        access="public_federal_business_opportunities_html",
        status="planned",
        priority=1,
        legal_reuse="YELLOW",
        machine_access="VERIFIED",
        expected_refresh_minutes=1440,
        stale_after_minutes=4320,
        capabilities=("search", "construction_filter"),
        signal_types=("TENDER",),
        adapter="UAEMoFDPPConnector",
        realtime_capable=False,
    ),
}


def source_status(name):
    return SOURCES.get(name, {"status": "unknown", "official": False})


def active_sources():
    """Return sources currently wired into the running sync pipeline."""
    return {k: v for k, v in SOURCES.items() if v["status"] == "active"}


def wave_sources(wave):
    """Return configured sources assigned to an implementation wave."""
    return {k: v for k, v in SOURCES.items() if v.get("wave") == wave}


def stale_after_minutes_for(name, default=15):
    """Return source-specific staleness SLA instead of one global threshold."""
    meta = SOURCES.get(name)
    if not meta:
        return int(default)
    return int(meta.get("stale_after_minutes") or default)


def production_gate_reasons(name):
    """Explain why a source may or may not be enabled for commercial ingestion."""
    meta = SOURCES.get(name)
    if not meta:
        return ("source_not_registered",)
    reasons = []
    if not meta.get("official"):
        reasons.append("not_official")
    if meta.get("machine_access") != "VERIFIED":
        reasons.append("machine_access_not_verified")
    if meta.get("legal_reuse") != "GREEN":
        reasons.append("commercial_reuse_not_green")
    if meta.get("status") not in ("active", "ready"):
        reasons.append("runtime_not_enabled")
    if not meta.get("adapter"):
        reasons.append("adapter_not_configured")
    return tuple(reasons)


def production_ready_sources():
    """Return only sources that pass every technical/legal/runtime gate."""
    return {k: v for k, v in SOURCES.items() if not production_gate_reasons(k)}