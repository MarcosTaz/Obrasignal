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
        kind="OPEN_DATA_INTERFACE",
        access="official_open_data",
        status="research",
        priority=2,
        legal_reuse="YELLOW",
        machine_access="VERIFIED",
        expected_refresh_minutes=60,
        stale_after_minutes=180,
        capabilities=("search", "incremental_sync"),
        adapter="GermanDOEAdapter",
        realtime_capable=True,
    ),
    "EC_SERCOP": _source(country="ECU", source_id="ec_sercop_ocds", kind="OCDS_API", access="api", status="planned", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=1440, stale_after_minutes=4320, capabilities=("search", "incremental_sync", "awards", "contracts", "plans"), signal_types=("PROCUREMENT_PLAN", "TENDER", "AWARD", "CONTRACT"), wave=1, adapter="OCDSAPIConnector"),
    "PY_DNCP": _source(country="PRY", source_id="py_dncp_api_v3", kind="OCDS_API", access="api", status="planned", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=60, stale_after_minutes=180, capabilities=("search", "incremental_sync", "awards", "contracts", "plans", "amendments"), signal_types=("PROCUREMENT_PLAN", "TENDER", "AWARD", "CONTRACT"), wave=1, adapter="OCDSAPIConnector", realtime_capable=True),
    "KR_KONEPS": _source(country="KOR", source_id="kr_koneps_openapi", kind="OPEN_DATA_API", access="api_key", status="planned", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=15, stale_after_minutes=60, capabilities=("search", "incremental_sync", "detail", "awards", "contracts", "lots"), wave=1, adapter="KONEPSAdapter", realtime_capable=True),
    "CH_SIMAP": _source(country="CHE", source_id="ch_simap_api", kind="OPEN_DATA_API", access="api", status="planned", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=60, stale_after_minutes=180, capabilities=("search", "incremental_sync", "detail", "awards"), wave=1, adapter="SimapAdapter", realtime_capable=True),
    "IT_ANAC": _source(country="ITA", source_id="it_anac_bdncp_open_data", kind="OPEN_DATA_API", access="api_and_bulk", status="planned", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=360, stale_after_minutes=1440, capabilities=("search", "incremental_sync", "awards", "contracts", "suppliers", "historical_data"), wave=1, adapter="ANACAdapter"),
    "UY_ARCE": _source(country="URY", source_id="uy_arce_ocds", kind="OCDS_API", access="api", status="planned", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=60, stale_after_minutes=180, capabilities=("search", "incremental_sync", "awards", "contracts", "plans"), signal_types=("PROCUREMENT_PLAN", "TENDER", "AWARD", "CONTRACT"), wave=1, adapter="OCDSAPIConnector", realtime_capable=True),
    "UK_PROCUREMENT": _source(country="GBR", source_id="uk_find_a_tender_contracts_finder", kind="OCDS_API", access="api_and_archives", status="planned", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=60, stale_after_minutes=180, capabilities=("search", "incremental_sync", "awards", "contracts", "historical_data"), wave=1, adapter="UKOCDSAdapter", realtime_capable=True),
    "LV_IUB": _source(country="LVA", source_id="lv_iub_open_data", kind="OFFICIAL_JSON_BULK", access="daily_json", status="planned", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=1440, stale_after_minutes=4320, capabilities=("incremental_sync", "awards", "historical_data"), wave=1, adapter="OfficialJSONBulkAdapter"),
    "ZA_ETENDERS": _source(country="ZAF", source_id="za_etenders_ocds", kind="OCDS_API", access="api_and_bulk", status="planned", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=1440, stale_after_minutes=4320, capabilities=("search", "incremental_sync", "awards", "historical_data"), wave=1, adapter="OCDSAPIConnector"),
    "PL_BZP": _source(country="POL", source_id="pl_ezamowienia_bzp_webservice", kind="PUBLIC_API", access="api", status="planned", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=60, stale_after_minutes=180, capabilities=("search", "incremental_sync", "plans", "awards"), signal_types=("PROCUREMENT_PLAN", "TENDER", "AWARD"), wave=1, adapter="PolandBZPAdapter", realtime_capable=True),
    "AT_KERNDATEN": _source(country="AUT", source_id="at_bvergg_kerndaten", kind="OPEN_MACHINE_DATA", access="catalogue_and_source", status="planned", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=60, stale_after_minutes=180, capabilities=("incremental_sync", "awards", "historical_data"), wave=1, adapter="AustriaKerndatenAdapter", realtime_capable=True),
    "NL_TENDERNED": _source(country="NLD", source_id="nl_tenderned", kind="OPEN_DATA_API", access="api_credentials", status="planned", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=60, stale_after_minutes=180, capabilities=("search", "incremental_sync", "awards", "historical_data"), wave=1, adapter="TenderNedAdapter", realtime_capable=True),
    "LT_VPT": _source(country="LTU", source_id="lt_vpt_cvp_is", kind="OPEN_DATA_API", access="api_and_bulk", status="planned", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=1440, stale_after_minutes=4320, capabilities=("incremental_sync", "awards", "contracts", "historical_data"), wave=1, adapter="LithuaniaVPTAdapter"),
    "EE_RHR": _source(country="EST", source_id="ee_rhr_public_api", kind="OFFICIAL_XML_EFORMS_BULK", access="monthly_open_data", status="planned", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=43200, stale_after_minutes=64800, capabilities=("incremental_sync", "awards", "historical_data"), wave=1, adapter="EFormsBulkAdapter"),
    "CO_SECOP": _source(country="COL", source_id="co_secop_open_data", kind="SOCRATA_ODATA", access="api", status="planned", priority=1, legal_reuse="GREEN", machine_access="VERIFIED", expected_refresh_minutes=1440, stale_after_minutes=4320, capabilities=("search", "incremental_sync", "awards", "contracts", "plans", "suppliers"), signal_types=("PROCUREMENT_PLAN", "TENDER", "AWARD", "CONTRACT"), wave=1, adapter="SocrataProcurementAdapter"),
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
