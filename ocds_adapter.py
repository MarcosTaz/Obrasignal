"""Reusable official Open Contracting Data Standard (OCDS) API connector.

The connector deliberately separates source transport/pagination from OCDS
normalization. Country-specific modules provide search parameters and auth,
while this module owns bounded incremental windows, page completeness checks,
optional record hydration, and conservative conversion of OCDS records/releases
into ObraSignal rows.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
from urllib.parse import quote

import requests


@dataclass(frozen=True)
class OCDSAPIConfig:
    source: str
    country: str
    search_url: str
    page_param: str = "page"
    page_size_param: str = "items_per_page"
    page_size: int = 100
    max_pages_per_window: int = 100
    window_days: int = 1
    max_windows_per_sync: int = 31
    initial_lookback_days: int = 7
    overlap_days: int = 1
    market: str = "GLOBAL"
    timeout: int = 45
    record_url_template: str | None = None
    hydrate_records: bool = False
    max_hydrations_per_window: int = 250


@dataclass(frozen=True)
class OCDSWindowCursor:
    completed_through: str

    def encode(self):
        return json.dumps(
            {"completed_through": self.completed_through},
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def decode(cls, value):
        if not value:
            return None
        text = str(value).strip()
        if text.startswith("{"):
            try:
                payload = json.loads(text)
                stamp = str(payload.get("completed_through") or "").strip()
                if stamp:
                    return cls(stamp)
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
        try:
            date.fromisoformat(text[:10])
        except ValueError:
            return None
        return cls(text[:10])


def _date(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _dig(mapping, *path):
    value = mapping
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _text(value):
    if value is None:
        return ""
    return str(value).strip()


def _records_from_payload(payload):
    """Extract OCDS record-like units from common API package shapes.

    Some official publishers wrap their useful body in a generic API envelope,
    e.g. ``{"payload": {"content": [...]}}``. Recursively unwrap only mapping
    payloads; this remains conservative and does not reinterpret scalar metadata.
    """
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        raise RuntimeError("OCDS API response is not an object/list")

    wrapped = payload.get("payload")
    if isinstance(wrapped, dict):
        content = wrapped.get("content")
        if isinstance(content, list):
            return [row for row in content if isinstance(row, dict)]
        if isinstance(content, dict):
            return _records_from_payload(content)
        nested = _records_from_payload(wrapped)
        if nested:
            return nested

    records = payload.get("records")
    if isinstance(records, list):
        return [row for row in records if isinstance(row, dict)]

    packages = payload.get("packages")
    if isinstance(packages, list):
        rows = []
        for package in packages:
            if isinstance(package, dict):
                rows.extend(_records_from_payload(package))
        return rows

    releases = payload.get("releases")
    if isinstance(releases, list):
        return [
            {"ocid": release.get("ocid"), "compiledRelease": release, "_package_uri": payload.get("uri")}
            for release in releases
            if isinstance(release, dict)
        ]

    for key in ("results", "items", "data"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]

    if payload.get("ocid") and (payload.get("compiledRelease") or payload.get("releases")):
        return [payload]
    return []


def _pagination_total_pages(payload):
    if not isinstance(payload, dict):
        return None
    pagination = payload.get("pagination")
    if not isinstance(pagination, dict):
        return None
    for key in ("total_pages", "totalPages", "pages"):
        value = pagination.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def _latest_release(record):
    compiled = record.get("compiledRelease") if isinstance(record, dict) else None
    if isinstance(compiled, dict):
        return compiled
    releases = record.get("releases") if isinstance(record, dict) else None
    if not isinstance(releases, list):
        return None
    candidates = [row for row in releases if isinstance(row, dict)]
    if not candidates:
        return None
    return max(candidates, key=lambda row: _text(row.get("date")))


def _first_classification(tender):
    items = tender.get("items") if isinstance(tender, dict) else None
    if isinstance(items, list):
        for item in items:
            classification = item.get("classification") if isinstance(item, dict) else None
            if isinstance(classification, dict) and classification.get("id"):
                return classification
    classification = tender.get("classification") if isinstance(tender, dict) else None
    return classification if isinstance(classification, dict) else {}


def _location_text(release, tender):
    addresses = []
    for candidate in (
        tender.get("deliveryAddress") if isinstance(tender, dict) else None,
        _dig(release, "buyer", "address"),
        _dig(release, "tender", "procuringEntity", "address"),
    ):
        if not isinstance(candidate, dict):
            continue
        parts = []
        for key in ("locality", "region", "postalCode", "countryName"):
            value = candidate.get(key)
            if isinstance(value, dict):
                value = value.get("name") or value.get("description")
            text = _text(value)
            if text and text not in parts:
                parts.append(text)
        if parts:
            addresses.append(" | ".join(parts))
    return addresses[0] if addresses else ""


def normalize_ocds_record(record, *, source, country, market="GLOBAL", require_active_tender=False):
    """Normalize one OCDS record/release without inventing taxonomy mappings."""
    if not isinstance(record, dict):
        return None
    release = _latest_release(record)
    if not isinstance(release, dict):
        return None
    tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
    ocid = _text(record.get("ocid") or release.get("ocid"))
    tender_id = _text(tender.get("id"))
    external_id = ocid or tender_id or _text(release.get("id"))
    if not external_id or not tender:
        return None

    status = _text(tender.get("statusDetails") or tender.get("status"))
    standard_status = _text(tender.get("status")).lower()
    if require_active_tender and standard_status != "active":
        return None

    classification = _first_classification(tender)
    scheme = _text(classification.get("scheme"))
    category_code = _text(classification.get("id"))
    is_cpv = scheme.upper().replace("-", "") in ("CPV", "CPV2008")
    cpv = category_code if is_cpv else ""
    taxonomy = "CPV" if is_cpv else (scheme or "OCDS_ITEM_CLASSIFICATION")

    buyer = release.get("buyer") if isinstance(release.get("buyer"), dict) else {}
    procuring = tender.get("procuringEntity") if isinstance(tender.get("procuringEntity"), dict) else {}
    buyer_name = _text(buyer.get("name") or procuring.get("name"))
    tender_period = tender.get("tenderPeriod") if isinstance(tender.get("tenderPeriod"), dict) else {}
    value = tender.get("value") if isinstance(tender.get("value"), dict) else {}
    release_date = _text(release.get("date"))
    tags = release.get("tag") if isinstance(release.get("tag"), list) else []
    main_category = _text(tender.get("mainProcurementCategoryDetails") or tender.get("mainProcurementCategory"))
    source_url = _text(tender.get("url") or record.get("uri") or record.get("_package_uri"))

    return {
        "source": source,
        "external_id": external_id,
        "title": _text(tender.get("title")),
        "description": _text(tender.get("description")),
        "buyer": buyer_name,
        "country": country,
        "cpv": cpv,
        "taxonomy": taxonomy,
        "category_code": category_code,
        "value": _text(value.get("amount")),
        "deadline": _text(tender_period.get("endDate")),
        "publication_date": release_date[:10] if release_date else "",
        "published_at": release_date or None,
        "source_updated_at": release_date or None,
        "url": source_url,
        "market": market,
        "place": _location_text(release, tender),
        "source_status": status,
        "source_phase": ",".join(_text(tag) for tag in tags if _text(tag)),
        "signal_type": "TENDER",
        "procurement_method": _text(tender.get("procurementMethodDetails") or tender.get("procurementMethod")),
        "contract_type": main_category,
        "source_reference": tender_id or _text(release.get("id")),
        "ocid": ocid,
        "ocds_tags": tags,
        "currency": _text(value.get("currency")),
        "classification_scheme": scheme,
    }


class OCDSAPIConnector:
    def __init__(self, config, *, params_factory, headers_provider=None, session=None):
        self.config = config
        self.params_factory = params_factory
        self.headers_provider = headers_provider
        self.session = session or requests.Session()

    def _headers(self):
        if self.headers_provider is None:
            return {}
        headers = self.headers_provider()
        if headers is None:
            return {}
        if not isinstance(headers, dict):
            raise RuntimeError(f"{self.config.source} auth provider did not return headers")
        return headers

    def _start_date(self, watermark, today):
        cursor = OCDSWindowCursor.decode(watermark)
        if cursor:
            parsed = _date(cursor.completed_through)
            if parsed:
                # completed_through is inclusive. The first unseen date is the
                # following day; overlap_days then deliberately replays the
                # requested number of already-completed days.
                return parsed + timedelta(days=1) - timedelta(days=max(0, self.config.overlap_days))
        return today - timedelta(days=max(0, self.config.initial_lookback_days))

    def _windows(self, watermark, now):
        today = _date(now or datetime.now(timezone.utc))
        start = self._start_date(watermark, today)
        width = max(1, int(self.config.window_days))
        count = 0
        while start <= today and count < max(1, int(self.config.max_windows_per_sync)):
            end = min(today, start + timedelta(days=width - 1))
            yield start, end
            start = end + timedelta(days=1)
            count += 1

    def _hydrate_candidate(self, candidate):
        if not self.config.hydrate_records:
            return candidate
        template = str(self.config.record_url_template or "").strip()
        if not template:
            raise RuntimeError(f"{self.config.source} hydration enabled without record_url_template")
        ocid = _text(candidate.get("ocid")) if isinstance(candidate, dict) else ""
        if not ocid:
            raise RuntimeError(f"{self.config.source} search candidate is missing ocid required for hydration")
        url = template.format(ocid=quote(ocid, safe=""))
        response = self.session.get(
            url,
            params={},
            headers=self._headers(),
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        package = response.json()
        records = _records_from_payload(package)
        if not records:
            raise RuntimeError(f"{self.config.source} hydration returned no OCDS record for {ocid}")
        for record in records:
            if _text(record.get("ocid")) == ocid:
                return record
        if len(records) == 1:
            return records[0]
        raise RuntimeError(f"{self.config.source} hydration response did not contain requested OCID {ocid}")

    def _hydrate_window(self, candidates, start, end):
        if not self.config.hydrate_records:
            return candidates
        unique = []
        seen = set()
        for candidate in candidates:
            ocid = _text(candidate.get("ocid")) if isinstance(candidate, dict) else ""
            identity = ocid or json.dumps(candidate, sort_keys=True, default=str)
            if identity in seen:
                continue
            seen.add(identity)
            unique.append(candidate)
        limit = max(1, int(self.config.max_hydrations_per_window))
        if len(unique) > limit:
            raise RuntimeError(
                f"{self.config.source} window {start}..{end} requires {len(unique)} record hydrations, "
                f"above max_hydrations_per_window={limit}; narrow the search or add a bulk strategy"
            )
        return [self._hydrate_candidate(candidate) for candidate in unique]

    def _fetch_window(self, start, end):
        candidates = []
        page = 1
        while page <= max(1, int(self.config.max_pages_per_window)):
            params = dict(self.params_factory(start, end) or {})
            params[self.config.page_param] = str(page)
            params[self.config.page_size_param] = str(self.config.page_size)
            response = self.session.get(
                self.config.search_url,
                params=params,
                headers=self._headers(),
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            batch = _records_from_payload(payload)
            total_pages = _pagination_total_pages(payload)
            if total_pages is not None and total_pages > self.config.max_pages_per_window:
                raise RuntimeError(
                    f"{self.config.source} window {start}..{end} has total_pages={total_pages}, "
                    f"above max_pages_per_window={self.config.max_pages_per_window}; narrow the query"
                )
            candidates.extend(batch)
            if total_pages is not None:
                if page >= total_pages:
                    return self._hydrate_window(candidates, start, end)
            elif not batch or len(batch) < self.config.page_size:
                return self._hydrate_window(candidates, start, end)
            page += 1

        raise RuntimeError(
            f"{self.config.source} reached max_pages_per_window={self.config.max_pages_per_window} "
            f"for {start}..{end}; cursor not advanced"
        )

    def fetch_incremental(self, normalizer, *, watermark=None, now=None):
        rows = []
        cursor = None
        for start, end in self._windows(watermark, now):
            batch = self._fetch_window(start, end)
            for record in batch:
                item = normalizer(record)
                if item and item.get("external_id"):
                    rows.append(item)
            cursor = OCDSWindowCursor(end.isoformat()).encode()
        return rows, cursor
