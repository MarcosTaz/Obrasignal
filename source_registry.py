"""Registry describing procurement sources and their verified coverage.

This is deliberately metadata-first: a country is not marked as integrated until
there is a verified machine-readable source and a tested connector. The UI/backend
can use this registry later to explain coverage honestly to users.
"""

SOURCES = {
    "TED": {
        "market": "EU",
        "countries": "EU",
        "status": "integrated",
        "kind": "official_api",
        "scope": "EU-level notices published through TED",
    },
    "BASE": {
        "market": "PT",
        "countries": ["PRT"],
        "status": "existing",
        "kind": "official_source",
        "scope": "Portuguese public procurement source already used by ObraSignal",
    },
    "BOAMP": {
        "market": "EU",
        "countries": ["FRA"],
        "status": "integrated",
        "kind": "official_open_data_api",
        "scope": "French BOAMP notices available through official open data",
    },
    "PLACSP": {
        "market": "EU",
        "countries": ["ESP"],
        "status": "integrated",
        "kind": "official_atom_feed",
        "scope": "Spanish notices exposed through the official procurement feed",
    },
    "PMP-LU": {
        "market": "EU",
        "countries": ["LUX"],
        "status": "verified_pending_endpoint",
        "kind": "official_portal_rss",
        "scope": "Luxembourg portal publishes notices and documents RSS feeds",
    },
    "BE_EPROC": {
        "market": "EU",
        "countries": ["BEL"],
        "status": "verified_pending_connector",
        "kind": "official_portal",
        "scope": "Belgian e-Procurement/e-Notification public procurement publications",
    },
}


def get_source(name):
    return SOURCES.get(name)


def integrated_sources():
    return {name: data for name, data in SOURCES.items() if data["status"] in {"integrated", "existing"}}


def coverage_status():
    return {
        "integrated": sorted(name for name, data in SOURCES.items() if data["status"] in {"integrated", "existing"}),
        "pending": sorted(name for name, data in SOURCES.items() if data["status"].startswith("verified_pending")),
    }
