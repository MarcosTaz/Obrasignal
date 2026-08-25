"""Complete publisher-native DGCP process discovery before bounded OCDS hydration.

The DGCP `/procesos` API is the complete, paginated process spine. It exposes the
publisher-owned `objeto_proceso` discriminator, including the exact value `Obras`.
Only those process rows are converted to the documented Dominican OCDS identity
(`ocds-6550wx-{codigo_proceso}`) and hydrated through the existing ReleasePackage
normalizer. This prevents broad N+1 OCDS hydration without inventing a keyword or
private construction taxonomy.

This module is transport glue for the existing `DO_DGCP` source. It does not
create a source identity, cursor, runtime, registry entry, or production switch.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import time

import requests

from dominican_republic_dgcp import (
    DGCP_API_ROOT,
    DGCP_CONFIG,
    normalize_dgcp_signals,
)
from ocds_release_lifecycle import OCDSReleasePackageConnector


DGCP_PROCESSES_URL = f"{DGCP_API_ROOT}/procesos"
DGCP_OCID_PREFIX = "ocds-6550wx-"
DGCP_WORKS_OBJECT = "obras"
DGCP_DETAIL_5XX_ATTEMPTS = 3


def dgcp_process_search_params(start, end):
    """Use only Swagger-documented publication-date filters for `/procesos`."""
    return {
        "startdate": start.isoformat(),
        "enddate": end.isoformat(),
    }


def _int_field(payload, name):
    value = payload.get(name) if isinstance(payload, dict) else None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise RuntimeError(f"DO_DGCP process response has invalid {name}") from None
    return parsed


def _publication_date(process):
    raw = str(process.get("fecha_publicacion") or "").strip()
    if not raw:
        raise RuntimeError("DO_DGCP process is missing fecha_publicacion")
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        raise RuntimeError("DO_DGCP process has invalid fecha_publicacion") from None


def _process_code(process):
    code = str(process.get("codigo_proceso") or "").strip()
    if not code:
        raise RuntimeError("DO_DGCP process is missing codigo_proceso")
    return code


def _is_publisher_works(process):
    return str(process.get("objeto_proceso") or "").strip().casefold() == DGCP_WORKS_OBJECT


def _candidate(process):
    code = _process_code(process)
    return {
        "ocid": f"{DGCP_OCID_PREFIX}{code}",
        "_dgcp_process_code": code,
        "_dgcp_object": str(process.get("objeto_proceso") or "").strip(),
        "_dgcp_subobject": str(process.get("subobjeto_proceso") or "").strip(),
        "_dgcp_publication_date": str(process.get("fecha_publicacion") or "").strip(),
    }


def _latest_tender_category(record):
    if not isinstance(record, dict):
        return ""
    compiled = record.get("compiledRelease")
    releases = [compiled] if isinstance(compiled, dict) else record.get("releases")
    if not isinstance(releases, list):
        return ""
    candidates = [release for release in releases if isinstance(release, dict) and isinstance(release.get("tender"), dict)]
    if not candidates:
        return ""
    latest = max(candidates, key=lambda release: str(release.get("date") or ""))
    return str(latest["tender"].get("mainProcurementCategory") or "").strip().casefold()


class DGCPProcessDiscoveryConnector(OCDSReleasePackageConnector):
    """Paginate every process in a date window, hydrate only publisher `Obras`."""

    def __init__(self, config=DGCP_CONFIG, *, session=None):
        super().__init__(
            config,
            params_factory=dgcp_process_search_params,
            session=session,
        )

    def _hydrate_candidate(self, candidate):
        """Retry only transient publisher 5xx detail failures, then fail closed."""
        for attempt in range(DGCP_DETAIL_5XX_ATTEMPTS):
            try:
                return super()._hydrate_candidate(candidate)
            except requests.HTTPError as exc:
                response = getattr(exc, "response", None)
                status = getattr(response, "status_code", None)
                retryable = isinstance(status, int) and 500 <= status <= 599
                if not retryable or attempt + 1 >= DGCP_DETAIL_5XX_ATTEMPTS:
                    raise
                time.sleep(0.25 * (attempt + 1))
        raise AssertionError("unreachable")

    def _process_page(self, start, end, page):
        params = dict(dgcp_process_search_params(start, end))
        params["page"] = str(page)
        params["limit"] = str(self.config.page_size)
        response = self.session.get(
            DGCP_PROCESSES_URL,
            params=params,
            headers=self._headers(),
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("DO_DGCP process response is not an object")
        if payload.get("code") != 200 or payload.get("hasError") is not False:
            raise RuntimeError("DO_DGCP process response reports an API error")

        body = payload.get("payload")
        rows = body.get("content") if isinstance(body, dict) else None
        page_value = _int_field(payload, "page")
        limit_value = _int_field(payload, "limit")

        # The live DGCP API has a distinct, proven no-results envelope:
        # page + limit are present, payload.content is null, while pages and
        # totalResults are omitted. Only that exact omission is normalized to
        # an empty page; partial/contradictory metadata remains an error.
        missing_pages = "pages" not in payload
        missing_total = "totalResults" not in payload
        if rows is None and missing_pages and missing_total:
            rows = []
            meta = {"page": page_value, "pages": 0, "limit": limit_value, "total": 0}
        else:
            if missing_pages or missing_total:
                raise RuntimeError("DO_DGCP process response has incomplete pagination metadata")
            meta = {
                "page": page_value,
                "pages": _int_field(payload, "pages"),
                "limit": limit_value,
                "total": _int_field(payload, "totalResults"),
            }
            if rows is None and meta["total"] == 0:
                rows = []

        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise RuntimeError("DO_DGCP process response has invalid payload.content")
        if meta["page"] != page:
            raise RuntimeError("DO_DGCP process response page does not match request")
        if meta["limit"] != int(self.config.page_size):
            raise RuntimeError("DO_DGCP process response limit does not match request")
        if meta["pages"] < 0 or meta["total"] < 0:
            raise RuntimeError("DO_DGCP process response has negative pagination metadata")
        if meta["pages"] == 0 and (meta["total"] != 0 or rows):
            raise RuntimeError("DO_DGCP zero-page response is internally inconsistent")
        if meta["pages"] > 0 and page > meta["pages"]:
            raise RuntimeError("DO_DGCP process response page exceeds total pages")
        if len(rows) > meta["limit"]:
            raise RuntimeError("DO_DGCP process response exceeds declared page limit")
        return rows, meta

    def _fetch_window(self, start, end):
        processes = []
        seen_codes = set()
        expected_pages = None
        expected_total = None
        page = 1

        while True:
            rows, meta = self._process_page(start, end, page)
            if meta["pages"] > int(self.config.max_pages_per_window):
                raise RuntimeError(
                    f"DO_DGCP process window {start}..{end} has pages={meta['pages']}, "
                    f"above max_pages_per_window={self.config.max_pages_per_window}; cursor not advanced"
                )
            if expected_pages is None:
                expected_pages, expected_total = meta["pages"], meta["total"]
            elif (meta["pages"], meta["total"]) != (expected_pages, expected_total):
                raise RuntimeError("DO_DGCP process pagination metadata changed during one window")

            for process in rows:
                code = _process_code(process)
                if code in seen_codes:
                    raise RuntimeError(f"DO_DGCP duplicate process identity in one window: {code}")
                seen_codes.add(code)
                published = _publication_date(process)
                if published < start or published > end:
                    raise RuntimeError(
                        f"DO_DGCP process {code} publication date {published} falls outside {start}..{end}"
                    )
                processes.append(process)

            if expected_pages == 0 or page >= expected_pages:
                break
            page += 1

        if len(processes) != expected_total:
            raise RuntimeError(
                f"DO_DGCP process window {start}..{end} fetched {len(processes)} rows "
                f"but publisher declared totalResults={expected_total}; cursor not advanced"
            )

        works_candidates = [_candidate(process) for process in processes if _is_publisher_works(process)]
        hydrated = self._hydrate_window(works_candidates, start, end)
        if len(hydrated) != len(works_candidates):
            raise RuntimeError("DO_DGCP hydration count does not match publisher works candidates")

        for candidate, record in zip(works_candidates, hydrated):
            expected_ocid = candidate["ocid"]
            actual_ocid = str(record.get("ocid") or "").strip() if isinstance(record, dict) else ""
            if actual_ocid != expected_ocid:
                raise RuntimeError(
                    f"DO_DGCP hydrated OCID {actual_ocid!r} does not match process-derived {expected_ocid!r}"
                )
            if _latest_tender_category(record) != "works":
                raise RuntimeError(
                    f"DO_DGCP publisher process {candidate['_dgcp_process_code']} is Obras "
                    "but hydrated OCDS tender is not mainProcurementCategory=works"
                )
        return hydrated


def dgcp_complete_connector(*, session=None):
    return DGCPProcessDiscoveryConnector(DGCP_CONFIG, session=session)


def fetch_dgcp_signals_complete(*, watermark=None, now=None, connector=None):
    """Complete process discovery -> publisher Obras -> bounded OCDS lifecycle signals."""
    client = connector or dgcp_complete_connector()
    return client.fetch_incremental_many(
        normalize_dgcp_signals,
        watermark=watermark,
        now=now or datetime.now(timezone.utc),
    )
