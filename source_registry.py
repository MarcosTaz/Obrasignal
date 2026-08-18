"""Verified procurement source registry for the European radar."""
SOURCES = {
    "TED": {"country": "EU", "official": True, "kind": "EU_API", "access": "search_api", "realtime_capable": True, "status": "active", "priority": 1},
    "BASE": {"country": "PRT", "official": True, "kind": "NATIONAL_PORTAL", "access": "existing_connector", "realtime_capable": False, "status": "active", "priority": 1},
    "BOAMP": {"country": "FRA", "official": True, "kind": "OPEN_DATA_API", "access": "api", "realtime_capable": True, "status": "active", "priority": 1},
    "PLACSP": {"country": "ESP", "official": True, "kind": "ATOM_FEED", "access": "feed", "realtime_capable": True, "status": "active", "priority": 1},
    "PMP-LU": {"country": "LUX", "official": True, "kind": "RSS", "access": "environment_configured", "realtime_capable": True, "status": "opt_in", "priority": 2},
    "SERVICE_BUND_DE": {"country": "DEU", "official": True, "kind": "NATIONAL_PORTAL", "access": "RSS_or_portal", "realtime_capable": True, "status": "research", "priority": 2},
}

def active_sources():
    return {k: v for k, v in SOURCES.items() if v["status"] == "active"}

def source_status(name):
    return SOURCES.get(name, {"status": "unknown", "official": False})
