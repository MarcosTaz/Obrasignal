"""UK Find a Tender public OCDS construction connector.

Find a Tender exposes release packages with opaque-cursor pagination and a
record-package endpoint containing the publisher-compiled current state. Release
windows are used only to discover affected OCIDs; every distinct OCID is hydrated
once per window before lifecycle/actionability is decided.
"""
from datetime import datetime, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

from ocds_cursor_adapter import OCDSOpaqueCursorAdapter, OCDSOpaqueCursorConfig


SOURCE = "UK_PROCUREMENT"
COUNTRY = "GBR"
FTS_RELEASE_URL = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
FTS_RECORD_URL = "https://www.find-tender.service.gov.uk/api/1.0/ocdsRecordPackages/{ocid}"
FTS_LICENSE = "http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
FTS_ATTRIBUTION = "Find a Tender service — UK Cabinet Office"
FTS_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal procurement connector/1.0 (+official open-data client)",
}
LONDON = ZoneInfo("Europe/London")


def _text(value):
    return "" if value is None else str(value).strip()


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _dt(value):
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _utc_now(value=None):
    parsed = _dt(value)
    return parsed or datetime.now(timezone.utc)


def _latest_source_release(record):
    releases = [row for row in _list(record.get("releases")) if isinstance(row, dict)]
    if not releases:
        return {}
    return max(releases, key=lambda row: _text(row.get("date")))


def _cpv_entries(items):
    entries = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        candidates = []
        classification = item.get("classification")
        if isinstance(classification, dict):
            candidates.append(classification)
        candidates.extend(row for row in _list(item.get("additionalClassifications")) if isinstance(row, dict))
        for classification in candidates:
            scheme = _text(classification.get("scheme")).upper().replace("-", "")
            code = _text(classification.get("id"))
            if scheme not in ("CPV", "CPV2008") or not code or code in seen:
                continue
            seen.add(code)
            entries.append({
                "id": code,
                "description": _text(classification.get("description")),
            })
    return entries


def _items_for_lot(tender, lot_id=None):
    items = [row for row in _list(tender.get("items")) if isinstance(row, dict)]
    if lot_id is None:
        return items
    return [row for row in items if _text(row.get("relatedLot")) == lot_id]


def _place(items, buyer):
    values = []
    for item in items:
        for address in _list(item.get("deliveryAddresses")):
            if not isinstance(address, dict):
                continue
            for key in ("locality", "region", "postalCode", "countryName", "country"):
                value = _text(address.get(key))
                if value and value not in values:
                    values.append(value)
    if not values:
        address = _dict(buyer.get("address"))
        for key in ("locality", "region", "postalCode", "countryName", "country"):
            value = _text(address.get(key))
            if value and value not in values:
                values.append(value)
    return " | ".join(values)


def _is_construction(tender):
    if _text(tender.get("mainProcurementCategory")).lower() == "works":
        return True
    return any(entry["id"].startswith("45") for entry in _cpv_entries(_items_for_lot(tender)))


def _actionability(tender_status, lot_status, deadline, now):
    process = _text(tender_status).lower()
    lot = _text(lot_status).lower()
    if process != "active":
        return False, process or "unknown", f"publisher tender status is {process or 'unknown'}"
    if lot and lot != "active":
        return False, lot, f"publisher lot status is {lot}"
    parsed_deadline = _dt(deadline)
    if parsed_deadline is None:
        return False, "active_no_deadline", "active tender has no valid submission deadline"
    if parsed_deadline <= now:
        return False, "deadline_elapsed", "submission deadline has elapsed"
    return True, "active", "publisher reports active tender and submission deadline is future"


def normalize_uk_record(record, *, now=None):
    """Normalize the publisher-compiled current state into lot-level observations."""
    if not isinstance(record, dict):
        return []
    ocid = _text(record.get("ocid"))
    compiled = record.get("compiledRelease") if isinstance(record.get("compiledRelease"), dict) else None
    if not ocid or compiled is None:
        raise RuntimeError("Find a Tender record package is missing ocid/compiledRelease")
    tender = compiled.get("tender") if isinstance(compiled.get("tender"), dict) else {}
    if not tender:
        return []
    if not _is_construction(tender):
        return []

    current = _utc_now(now)
    buyer = compiled.get("buyer") if isinstance(compiled.get("buyer"), dict) else {}
    latest_release = _latest_source_release(record)
    notice_id = _text(latest_release.get("id"))
    source_updated_at = _text(compiled.get("date") or latest_release.get("date"))
    tender_status = _text(tender.get("status"))
    deadline = _text(_dict(tender.get("tenderPeriod")).get("endDate"))
    method = _text(tender.get("procurementMethodDetails") or tender.get("procurementMethod"))
    category = _text(tender.get("mainProcurementCategory"))
    tender_value = _dict(tender.get("value"))
    source_url = (
        f"{FTS_RELEASE_URL}/{quote(notice_id, safe='')}" if notice_id
        else FTS_RECORD_URL.format(ocid=quote(ocid, safe=""))
    )

    lots = [row for row in _list(tender.get("lots")) if isinstance(row, dict)]
    if not lots:
        lots = [None]

    observations = []
    for lot in lots:
        lot_id = _text(lot.get("id")) if isinstance(lot, dict) else ""
        if lot is not None and not lot_id:
            raise RuntimeError(f"Find a Tender construction record {ocid} contains a lot without id")
        external_id = f"{ocid}:lot:{lot_id}" if lot_id else ocid
        lot_items = _items_for_lot(tender, lot_id if lot is not None else None)
        cpvs = _cpv_entries(lot_items)
        # If a lot has no linked classifications, preserve process-level CPV
        # evidence rather than inventing a classification for the lot.
        if not cpvs:
            cpvs = _cpv_entries(_items_for_lot(tender))
        primary_cpv = cpvs[0]["id"] if cpvs else ""
        lot_value = _dict(lot.get("value")) if isinstance(lot, dict) else {}
        value = lot_value or tender_value
        lot_status = _text(lot.get("status")) if isinstance(lot, dict) else ""
        actionable, lifecycle_status, lifecycle_reason = _actionability(
            tender_status, lot_status, deadline, current
        )

        base_title = _text(tender.get("title"))
        lot_title = _text(lot.get("title") or lot.get("description")) if isinstance(lot, dict) else ""
        title = base_title
        if lot is not None and lot_title and lot_title != base_title:
            title = f"{base_title} — Lot {lot_id}: {lot_title}"

        observation = {
            "source": SOURCE,
            "external_id": external_id,
            "title": title,
            "description": _text((lot or {}).get("description") if isinstance(lot, dict) else "") or _text(tender.get("description")),
            "buyer": _text(buyer.get("name")),
            "country": COUNTRY,
            "cpv": primary_cpv,
            "taxonomy": "CPV" if primary_cpv else "",
            "category_code": primary_cpv,
            "cpv_codes": [row["id"] for row in cpvs],
            "cpv_classifications": cpvs,
            "value": _text(value.get("amount")),
            "currency": _text(value.get("currency")),
            "deadline": deadline,
            "publication_date": source_updated_at[:10] if source_updated_at else "",
            "published_at": source_updated_at or None,
            "source_updated_at": source_updated_at or None,
            "url": source_url,
            "market": "GLOBAL",
            "place": _place(lot_items, buyer),
            "source_status": tender_status,
            "source_phase": ",".join(_text(tag) for tag in _list(compiled.get("tag")) if _text(tag)),
            "signal_type": "TENDER",
            "procurement_method": method,
            "contract_type": category,
            "source_reference": notice_id or _text(compiled.get("id")),
            "notice_identifier": notice_id,
            "ocid": ocid,
            "lot_id": lot_id,
            "lot_status": lot_status,
            "sme_suitable": _dict((lot or {}).get("suitability") if isinstance(lot, dict) else {}).get("sme"),
            "license": FTS_LICENSE,
            "attribution": FTS_ATTRIBUTION,
            "source_dataset": "Find a Tender OCDS output",
            "source_modified": True,
            "is_actionable": actionable,
            "lifecycle_status": lifecycle_status,
            "lifecycle_reason": lifecycle_reason,
        }
        if not actionable:
            observation["_lifecycle_only"] = True
        observations.append(observation)
    return observations


class UKFindTenderConnector:
    def __init__(self, *, session=None, max_hydrations_per_window=250):
        self.session = session or requests.Session()
        self.max_hydrations_per_window = max(1, int(max_hydrations_per_window))
        config = OCDSOpaqueCursorConfig(
            source=SOURCE,
            country=COUNTRY,
            search_url=FTS_RELEASE_URL,
            page_size=100,
            max_pages_per_window=10,
            max_windows_per_sync=24,
            window_minutes=15,
            initial_lookback_minutes=14 * 24 * 60,
            overlap_minutes=5,
            timeout=45,
        )
        self.transport = OCDSOpaqueCursorAdapter(
            config,
            params_factory=self._params,
            window_processor=self._process_release_window,
            session=self.session,
            headers=FTS_HEADERS,
        )

    @staticmethod
    def _format_timestamp(value):
        if not isinstance(value, datetime):
            raise RuntimeError("Find a Tender subdaily window requires datetime bounds")
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        # Live validation on 2026-08-24 proved that updatedFrom/updatedTo are
        # filtered against the UK publication clock: 10:05Z did NOT retrieve a
        # release stamped 11:13+01, while 11:05+01 did. Keep durable cursors UTC,
        # but express the source query in Europe/London with its explicit DST
        # offset so BST/GMT transitions are handled by the timezone database.
        return value.astimezone(LONDON).isoformat(timespec="seconds")

    def _params(self, start, end):
        # No server-side `stages` filter: a live 2026 validation showed a current
        # tender release present in the unfiltered window while `stages=tender`
        # returned an empty package for the same time range. Filter current state
        # only after authoritative record hydration.
        return {
            "updatedFrom": self._format_timestamp(start),
            "updatedTo": self._format_timestamp(end),
        }

    def _hydrate_record(self, ocid):
        url = FTS_RECORD_URL.format(ocid=quote(ocid, safe=""))
        response = self.session.get(url, params={}, headers=FTS_HEADERS, timeout=45)
        response.raise_for_status()
        payload = response.json()
        records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(records, list) or not records:
            raise RuntimeError(f"Find a Tender record package returned no record for {ocid}")
        for record in records:
            if isinstance(record, dict) and _text(record.get("ocid")) == ocid:
                if not isinstance(record.get("compiledRelease"), dict):
                    raise RuntimeError(f"Find a Tender record {ocid} has no compiledRelease")
                return record
        raise RuntimeError(f"Find a Tender record package did not contain requested OCID {ocid}")

    def _process_release_window(self, releases, *, start, end, now=None):
        ocids = []
        seen = set()
        for release in releases:
            ocid = _text(release.get("ocid")) if isinstance(release, dict) else ""
            if not ocid:
                raise RuntimeError(f"Find a Tender release in {start}..{end} is missing ocid")
            if ocid in seen:
                continue
            seen.add(ocid)
            ocids.append(ocid)
        if len(ocids) > self.max_hydrations_per_window:
            raise RuntimeError(
                f"Find a Tender window {start}..{end} requires {len(ocids)} record hydrations, "
                f"above max_hydrations_per_window={self.max_hydrations_per_window}; cursor not advanced"
            )
        observations = []
        for ocid in ocids:
            observations.extend(normalize_uk_record(self._hydrate_record(ocid), now=now))
        return observations

    def fetch_incremental(self, *, watermark=None, now=None):
        return self.transport.fetch_incremental(watermark=watermark, now=now)


def build_uk_connector(*, session=None, max_hydrations_per_window=250):
    return UKFindTenderConnector(session=session, max_hydrations_per_window=max_hydrations_per_window)


def fetch_uk_tenders(*, watermark=None, now=None, connector=None):
    client = connector or build_uk_connector()
    return client.fetch_incremental(watermark=watermark, now=now)
