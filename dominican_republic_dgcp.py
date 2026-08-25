"""Dominican Republic DGCP OCDS construction procurement source.

The official DGCP API uses a two-step transport in live operation:
``/ocds/releases/all`` returns a paginated generic envelope containing OCID/detail
URL candidates, then ``/ocds/releases?ocid=...`` returns the OCDS release package.
This module is intentionally a thin market configuration on top of the reusable
:mod:`ocds_adapter` family; it does not create another connector framework.

Publisher documentation (Swagger 2.0):
https://datosabiertos.dgcp.gob.do/api-dgcp/docs/doc.json

The API documentation declares Apache-2.0 and states that the backing data
warehouse refreshes four times per day. Public discovery + detail machine access
was live-proven from GitHub Actions on 2026-08-25. Production promotion remains
separately gated until full-window pagination/completeness and sustainable
hydration volume are validated.
"""
from datetime import datetime, timezone

from ocds_adapter import OCDSAPIConfig, OCDSAPIConnector, normalize_ocds_record


DGCP_API_ROOT = "https://datosabiertos.dgcp.gob.do/api-dgcp/v1"
DGCP_OCDS_RELEASES_URL = f"{DGCP_API_ROOT}/ocds/releases/all"
DGCP_OCDS_DETAIL_URL_TEMPLATE = f"{DGCP_API_ROOT}/ocds/releases?ocid={{ocid}}"
DGCP_PORTAL_URL = "https://datosabiertos.dgcp.gob.do/"
DGCP_LICENSE = "Apache-2.0"
DGCP_ATTRIBUTION = "Dirección General de Contrataciones Públicas (DGCP) — República Dominicana"


DGCP_CONFIG = OCDSAPIConfig(
    source="DO_DGCP",
    country="DOM",
    search_url=DGCP_OCDS_RELEASES_URL,
    page_param="page",
    page_size_param="limit",
    # The publisher documents a maximum limit of 1000. A smaller page keeps
    # response and per-request hydration pressure bounded while completeness is
    # validated. The whole temporal window still fails closed above the bound.
    page_size=200,
    max_pages_per_window=100,
    window_days=1,
    max_windows_per_sync=14,
    initial_lookback_days=7,
    overlap_days=1,
    market="GLOBAL",
    timeout=45,
    record_url_template=DGCP_OCDS_DETAIL_URL_TEMPLATE,
    hydrate_records=True,
    max_hydrations_per_window=250,
)


def dgcp_search_params(start, end):
    """Return only publisher-documented date filters.

    DGCP does not document a server-side ``works`` parameter on the OCDS
    discovery endpoint, so construction admission happens on the publisher-native
    OCDS ``mainProcurementCategory`` after bounded detail hydration. We
    deliberately do not substitute keyword matching.
    """
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }


def _latest_release(record):
    if not isinstance(record, dict):
        return None
    compiled = record.get("compiledRelease")
    if isinstance(compiled, dict):
        return compiled
    releases = record.get("releases")
    if isinstance(releases, list):
        candidates = [value for value in releases if isinstance(value, dict)]
        if candidates:
            return max(candidates, key=lambda value: str(value.get("date") or ""))
    return None


def normalize_dgcp_process(record):
    """Normalize one active DGCP works tender without inventing taxonomy maps."""
    release = _latest_release(record)
    tender = release.get("tender") if isinstance(release, dict) else None
    if not isinstance(tender, dict):
        return None

    if str(tender.get("mainProcurementCategory") or "").strip().lower() != "works":
        return None

    item = normalize_ocds_record(
        record,
        source="DO_DGCP",
        country="DOM",
        market="GLOBAL",
        require_active_tender=True,
    )
    if not item:
        return None
    item["url"] = item.get("url") or DGCP_PORTAL_URL
    item["license"] = DGCP_LICENSE
    item["attribution"] = DGCP_ATTRIBUTION
    item["source_dataset"] = "DGCP API — OCDS releases"
    item["source_modified"] = True
    return item


def dgcp_connector(*, session=None):
    return OCDSAPIConnector(
        DGCP_CONFIG,
        params_factory=dgcp_search_params,
        session=session,
    )


def fetch_dgcp_processes(*, watermark=None, now=None, connector=None):
    client = connector or dgcp_connector()
    return client.fetch_incremental(
        normalize_dgcp_process,
        watermark=watermark,
        now=now or datetime.now(timezone.utc),
    )
