"""Uruguay ARCE procurement connector using the official OCDS RSS index.

ARCE publishes a current RSS index, monthly RSS recovery routes, record indexes
by purchase id, and individual OCDS release packages. Its record endpoint links
to releases rather than publishing a compiledRelease, so this connector hydrates
a bounded tender release history and merges partial updates before normalization.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import calendar
import json
import re
import xml.etree.ElementTree as ET

import requests

from ocds_adapter import normalize_ocds_record


ARCE_RSS_URL = "https://www.comprasestatales.gub.uy/ocds/rss"
ARCE_RECORD_ROOT = "https://www.comprasestatales.gub.uy/ocds/record"
ARCE_HEADERS = {
    "User-Agent": "ObraSignal procurement connector/1.0 (+official open-data client)",
    "Accept": "application/rss+xml, application/xml;q=0.9, application/json;q=0.9, */*;q=0.1",
}
ARCE_LICENSE = "Licencia de Datos Abiertos - Uruguay"
ARCE_ATTRIBUTION = "Agencia Reguladora de Compras Estatales (ARCE) — Open Contracting / Compras Estatales"


@dataclass(frozen=True)
class ARCEEvent:
    published_at: str
    guid: str
    category: str
    title: str
    link: str
    purchase_id: str

    def key(self):
        return (_parse_iso(self.published_at), self.guid)


@dataclass(frozen=True)
class ARCECursor:
    published_at: str
    guid: str = ""

    def encode(self):
        return json.dumps(
            {"published_at": self.published_at, "guid": self.guid},
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
                published_at = str(payload.get("published_at") or "").strip()
                guid = str(payload.get("guid") or "").strip()
                if published_at and _parse_iso(published_at):
                    return cls(published_at, guid)
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
        parsed = _parse_iso(text)
        return cls(_iso(parsed), "") if parsed else None


def _local(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _child_text(node, name):
    for child in node:
        if _local(child.tag) == name:
            return (child.text or "").strip()
    return ""


def _parse_iso(value):
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value):
    parsed = _parse_iso(value)
    return parsed.isoformat().replace("+00:00", "Z") if parsed else ""


def _parse_rss_date(value):
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        # Live ARCE RSS timestamps match the associated OCDS UTC release time
        # but omit an RFC timezone token.
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def purchase_id_from_title(title):
    match = re.search(r"(?:^|,)\s*id_compra\s*:\s*([^,\s]+)", str(title or ""), flags=re.I)
    return match.group(1) if match else ""


def parse_arce_rss(content):
    if isinstance(content, str):
        content = content.encode("utf-8")
    root = ET.fromstring(content)
    if _local(root.tag) != "rss":
        raise RuntimeError(f"UY_ARCE expected RSS root, got {_local(root.tag)!r}")
    channel = next((node for node in root if _local(node.tag) == "channel"), None)
    if channel is None:
        raise RuntimeError("UY_ARCE RSS did not contain channel")
    events = []
    for item in channel:
        if _local(item.tag) != "item":
            continue
        published = _parse_rss_date(_child_text(item, "pubDate"))
        guid = _child_text(item, "guid")
        if not published or not guid:
            continue
        title = _child_text(item, "title")
        events.append(
            ARCEEvent(
                published_at=_iso(published),
                guid=guid,
                category=_child_text(item, "category"),
                title=title,
                link=_child_text(item, "link").replace("http://", "https://", 1),
                purchase_id=purchase_id_from_title(title),
            )
        )
    events.sort(key=lambda event: event.key())
    return events


def monthly_rss_url(moment):
    parsed = _parse_iso(moment)
    if not parsed:
        raise ValueError("valid month timestamp required")
    return f"{ARCE_RSS_URL}/{parsed.year:04d}/{parsed.month:02d}"


def _month_end(moment):
    parsed = _parse_iso(moment)
    last_day = calendar.monthrange(parsed.year, parsed.month)[1]
    return datetime(parsed.year, parsed.month, last_day, 23, 59, 59, tzinfo=timezone.utc)


def _merge_list(base, patch):
    base = deepcopy(base) if isinstance(base, list) else []
    patch = deepcopy(patch)
    if not patch:
        return patch
    combined = base + patch
    if all(isinstance(item, dict) and item.get("id") is not None for item in combined):
        order = []
        indexed = {}
        for item in combined:
            identity = str(item.get("id"))
            if identity not in indexed:
                indexed[identity] = deepcopy(item)
                order.append(identity)
            else:
                indexed[identity] = _merge_value(indexed[identity], item)
        return [indexed[identity] for identity in order]
    return patch


def _merge_value(base, patch):
    """Merge partial OCDS state: omitted fields remain, explicit fields win."""
    if patch is None:
        return None
    if isinstance(patch, dict):
        result = deepcopy(base) if isinstance(base, dict) else {}
        for key, value in patch.items():
            result[key] = _merge_value(result.get(key), value)
        return result
    if isinstance(patch, list):
        return _merge_list(base, patch)
    return deepcopy(patch)


def merge_arce_releases(releases):
    candidates = [release for release in releases or [] if isinstance(release, dict)]
    candidates.sort(key=lambda release: str(release.get("date") or ""))
    if not candidates:
        return None
    merged = {}
    tags = []
    for release in candidates:
        merged = _merge_value(merged, release)
        for tag in release.get("tag") or []:
            text = str(tag or "").strip()
            if text and text not in tags:
                tags.append(text)
    merged["tag"] = tags
    merged["date"] = candidates[-1].get("date") or merged.get("date")
    return merged


def _extract_record(package, purchase_id):
    records = package.get("records") if isinstance(package, dict) else None
    if not isinstance(records, list) or not records:
        raise RuntimeError(f"UY_ARCE record {purchase_id} returned no records")
    records = [record for record in records if isinstance(record, dict)]
    if len(records) == 1:
        return records[0]
    for record in records:
        if str(record.get("ocid") or "").endswith(f"-{purchase_id}"):
            return record
    raise RuntimeError(f"UY_ARCE record response did not identify purchase {purchase_id}")


def _release_from_package(package, url):
    releases = package.get("releases") if isinstance(package, dict) else None
    if not isinstance(releases, list) or not releases:
        raise RuntimeError(f"UY_ARCE release endpoint returned no releases: {url}")
    candidates = [release for release in releases if isinstance(release, dict)]
    if not candidates:
        raise RuntimeError(f"UY_ARCE release endpoint returned invalid release: {url}")
    return candidates[0]


def _deadline_open(deadline, now):
    parsed = _parse_iso(deadline)
    current = _parse_iso(now or datetime.now(timezone.utc))
    return bool(parsed and current and parsed > current)


def normalize_arce_process(record, *, purchase_id, now=None):
    item = normalize_ocds_record(
        record,
        source="UY_ARCE",
        country="URY",
        market="GLOBAL",
        require_active_tender=True,
    )
    if not item or not _deadline_open(item.get("deadline"), now):
        return None
    item["url"] = f"{ARCE_RECORD_ROOT}/{purchase_id}"
    item["source_reference"] = purchase_id
    item["license"] = ARCE_LICENSE
    item["attribution"] = ARCE_ATTRIBUTION
    item["source_dataset"] = "Open Contracting / Compras Estatales"
    item["source_modified"] = True
    return item


class ARCEOCDSRSSAdapter:
    def __init__(
        self,
        *,
        session=None,
        timeout=30,
        initial_lookback_hours=72,
        overlap_seconds=2,
        max_events_per_sync=100,
        max_release_refs_per_process=50,
    ):
        self.session = session or requests.Session()
        self.timeout = int(timeout)
        self.initial_lookback_hours = int(initial_lookback_hours)
        self.overlap_seconds = int(overlap_seconds)
        self.max_events_per_sync = int(max_events_per_sync)
        self.max_release_refs_per_process = int(max_release_refs_per_process)

    def _get(self, url):
        response = self.session.get(url, headers=ARCE_HEADERS, timeout=self.timeout)
        response.raise_for_status()
        return response

    def _feed(self, url):
        return parse_arce_rss(self._get(url).content)

    def _event_batch(self, watermark, now):
        current = _parse_iso(now or datetime.now(timezone.utc))
        cursor = ARCECursor.decode(watermark)
        cursor_dt = _parse_iso(cursor.published_at) if cursor else None
        live_events = self._feed(ARCE_RSS_URL)

        if not cursor_dt:
            cutoff = current - timedelta(hours=max(1, self.initial_lookback_hours))
            eligible = [event for event in live_events if _parse_iso(event.published_at) >= cutoff]
            batch = eligible[: max(1, self.max_events_per_sync)]
            if not batch:
                return [], ARCECursor(_iso(current), "")
            return batch, ARCECursor(batch[-1].published_at, batch[-1].guid)

        # The RSS is an immutable release-event index. Progress therefore uses
        # the strict (pubDate, guid) key, not a replay window. The time overlap
        # is retained only when deciding whether the cursor is still safely
        # covered by the current last-500 feed horizon.
        cursor_key = (cursor_dt, cursor.guid or "")
        horizon_probe = cursor_dt - timedelta(seconds=max(0, self.overlap_seconds))
        oldest_live = _parse_iso(live_events[0].published_at) if live_events else None
        if oldest_live and horizon_probe >= oldest_live:
            eligible = [event for event in live_events if event.key() > cursor_key]
            batch = eligible[: max(1, self.max_events_per_sync)]
            if not batch:
                return [], cursor
            return batch, ARCECursor(batch[-1].published_at, batch[-1].guid)

        # Current RSS contains only the most recent 500 releases. A cursor older
        # than that visible horizon switches to the documented /rss/YYYY/MM
        # recovery route. A completed historical month is marked with guid '~';
        # the following run starts one second later, in the next month.
        recovery_start = cursor_dt + timedelta(seconds=1) if cursor.guid == "~" else cursor_dt
        recovery_events = self._feed(monthly_rss_url(recovery_start))
        if cursor.guid == "~":
            eligible = [event for event in recovery_events if _parse_iso(event.published_at) >= recovery_start]
        else:
            eligible = [event for event in recovery_events if event.key() > cursor_key]
        batch = eligible[: max(1, self.max_events_per_sync)]
        if len(eligible) > len(batch):
            return batch, ARCECursor(batch[-1].published_at, batch[-1].guid)

        month_end = _month_end(recovery_start)
        if month_end < current:
            return batch, ARCECursor(_iso(month_end), "~")
        if batch:
            return batch, ARCECursor(batch[-1].published_at, batch[-1].guid)
        return [], cursor

    def _record_index(self, purchase_id):
        return _extract_record(self._get(f"{ARCE_RECORD_ROOT}/{purchase_id}").json(), purchase_id)

    def _hydrate_tender_state(self, purchase_id):
        record = self._record_index(purchase_id)
        refs = [
            ref
            for ref in (record.get("releases") or [])
            if isinstance(ref, dict)
            and ref.get("url")
            and any(str(tag or "").lower().startswith("tender") for tag in (ref.get("tag") or []))
        ]
        refs.sort(key=lambda ref: str(ref.get("date") or ""))
        if not refs:
            raise RuntimeError(f"UY_ARCE purchase {purchase_id} has no tender release references")
        if len(refs) > max(1, self.max_release_refs_per_process):
            raise RuntimeError(
                f"UY_ARCE purchase {purchase_id} requires {len(refs)} tender releases, "
                f"above max_release_refs_per_process={self.max_release_refs_per_process}"
            )
        releases = []
        for ref in refs:
            url = str(ref.get("url")).replace("http://", "https://", 1)
            releases.append(_release_from_package(self._get(url).json(), url))
        compiled = merge_arce_releases(releases)
        if not compiled:
            raise RuntimeError(f"UY_ARCE purchase {purchase_id} could not reconstruct tender state")
        return {
            "ocid": record.get("ocid") or compiled.get("ocid"),
            "compiledRelease": compiled,
            "uri": f"{ARCE_RECORD_ROOT}/{purchase_id}",
        }

    def fetch_incremental(self, *, watermark=None, now=None):
        current = _parse_iso(now or datetime.now(timezone.utc))
        events, next_cursor = self._event_batch(watermark, current)
        purchase_ids = []
        seen = set()
        for event in events:
            if not str(event.category or "").lower().startswith("tender"):
                continue
            if not event.purchase_id:
                raise RuntimeError(f"UY_ARCE tender event {event.guid} is missing id_compra")
            if event.purchase_id not in seen:
                seen.add(event.purchase_id)
                purchase_ids.append(event.purchase_id)

        rows = []
        for purchase_id in purchase_ids:
            state = self._hydrate_tender_state(purchase_id)
            item = normalize_arce_process(state, purchase_id=purchase_id, now=current)
            if item:
                rows.append(item)
        return rows, next_cursor.encode() if next_cursor else watermark


def fetch_arce_tenders(*, watermark=None, now=None, adapter=None):
    client = adapter or ARCEOCDSRSSAdapter()
    return client.fetch_incremental(watermark=watermark, now=now)
