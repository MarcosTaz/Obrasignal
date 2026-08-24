"""Paraguay DNCP v3 OCDS construction procurement source.

Official API contract:
https://www.contrataciones.gov.py/datos/api/v3/doc/

The production API requires an application/request token. Anonymous access is
reserved for low-rate testing by the publisher, so production helpers fail
closed when credentials are absent.

DNCP `/search/processes` deliberately returns a minimal OCDS record package.
This source therefore uses search only for bounded candidate discovery, then
hydrates each OCID through the official `/ocds/record/{ocid}` record-package
endpoint before deciding whether to emit a live TENDER signal.
"""
from datetime import datetime, timezone
import os
import time

import requests

from ocds_adapter import OCDSAPIConfig, OCDSAPIConnector, normalize_ocds_record


DNCP_API_ROOT = "https://www.contrataciones.gov.py/datos/api/v3/doc"
DNCP_SEARCH_URL = f"{DNCP_API_ROOT}/search/processes"
DNCP_TOKEN_URL = f"{DNCP_API_ROOT}/oauth/token"
DNCP_RECORD_URL_TEMPLATE = f"{DNCP_API_ROOT}/ocds/record/{{ocid}}"
DNCP_PORTAL_URL = "https://www.contrataciones.gov.py/buscador/licitaciones.html"

DNCP_CONFIG = OCDSAPIConfig(
    source="PY_DNCP",
    country="PRY",
    search_url=DNCP_SEARCH_URL,
    page_size=100,
    # The publisher caps list services at 10,000 results. With active works +
    # one-day release windows, 100 pages x 100 records reaches that ceiling and
    # must fail closed rather than pretend a truncated window is complete.
    max_pages_per_window=100,
    window_days=1,
    max_windows_per_sync=14,
    initial_lookback_days=7,
    overlap_days=1,
    market="GLOBAL",
    timeout=45,
    record_url_template=DNCP_RECORD_URL_TEMPLATE,
    hydrate_records=True,
    # Hydration is intentionally bounded. A larger candidate window requires
    # query narrowing or a bulk strategy, not thousands of detail calls.
    max_hydrations_per_window=250,
)


def dncp_search_params(start, end):
    return {
        "fecha_desde": start.isoformat(),
        "fecha_hasta": end.isoformat(),
        "tipo_fecha": "fecha_release",
        "tender.mainProcurementCategory": "works",
        # Live validation confirmed DNCP accepts the standard OCDS status field
        # for search even though the minimal response omits it. Hydration then
        # verifies the final compiled tender state before emission.
        "tender.status": "active",
        "order": "date asc",
    }


class DNCPTokenProvider:
    """Short-lived DNCP v3 access-token provider.

    ``DNCP_ACCESS_TOKEN`` can be used when deployment already manages token
    rotation. Otherwise ``DNCP_REQUEST_TOKEN`` is exchanged against the
    official v3 ``/oauth/token`` endpoint and cached for 14 minutes, below the
    publisher's documented 15-minute token lifetime.
    """

    def __init__(self, *, session=None, allow_anonymous=False):
        self.session = session or requests.Session()
        self.allow_anonymous = bool(allow_anonymous)
        self._cached_token = None
        self._expires_at = 0.0

    def _direct_token(self):
        return os.getenv("DNCP_ACCESS_TOKEN", "").strip()

    def _request_token(self):
        return os.getenv("DNCP_REQUEST_TOKEN", "").strip()

    def _exchange(self, request_token):
        response = self.session.post(
            DNCP_TOKEN_URL,
            json={"request_token": request_token},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("PY_DNCP token response is not an object")
        token = str(payload.get("access_token") or payload.get("token") or "").strip()
        if not token:
            raise RuntimeError("PY_DNCP token response did not contain access_token")
        self._cached_token = token
        self._expires_at = time.monotonic() + (14 * 60)
        return token

    def headers(self):
        direct = self._direct_token()
        if direct:
            return {"Authorization": direct}

        if self._cached_token and time.monotonic() < self._expires_at:
            return {"Authorization": self._cached_token}

        request_token = self._request_token()
        if request_token:
            return {"Authorization": self._exchange(request_token)}

        if self.allow_anonymous:
            return {}
        raise RuntimeError(
            "PY_DNCP production access requires DNCP_REQUEST_TOKEN or DNCP_ACCESS_TOKEN"
        )


def normalize_dncp_process(record):
    item = normalize_ocds_record(
        record,
        source="PY_DNCP",
        country="PRY",
        market="GLOBAL",
        require_active_tender=True,
    )
    if not item:
        return None
    # Preserve the publisher's richer local category label when present; only
    # fall back to the standard OCDS code when the source gives no details.
    item["contract_type"] = item.get("contract_type") or "works"
    item["url"] = item.get("url") or DNCP_PORTAL_URL
    return item


def dncp_connector(*, session=None, allow_anonymous=False):
    transport = session or requests.Session()
    auth = DNCPTokenProvider(session=transport, allow_anonymous=allow_anonymous)
    return OCDSAPIConnector(
        DNCP_CONFIG,
        params_factory=dncp_search_params,
        headers_provider=auth.headers,
        session=transport,
    )


def fetch_dncp_processes(*, watermark=None, now=None, connector=None, allow_anonymous=False):
    client = connector or dncp_connector(allow_anonymous=allow_anonymous)
    return client.fetch_incremental(
        normalize_dncp_process,
        watermark=watermark,
        now=now or datetime.now(timezone.utc),
    )
