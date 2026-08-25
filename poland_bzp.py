"""Poland e-Zamowienia BZP public construction-notice connector.

BZP has no effective page-number pagination. Completeness is proved with the
companion ``/stats`` endpoint: a time interval is accepted only when each notice
list exactly matches the publisher count; oversized intervals are split until
complete. ``tenderId`` is the stable procedure identity and ``objectId`` is the
publication identity used by the public detail page.

Only publisher-native ``orderType == 'Works'`` ContractNotice records can create
an opportunity. NoticeUpdateNotice omits order type, CPV and summary deadline,
so it is applied only to already tracked construction procedures. Section 8.1
submission-deadline changes are parsed from the exact ``Przed zmianą`` / ``Po
zmianie`` HTML sequence in Europe/Warsaw time. TenderResultNotice closes a
tracked opportunity. Raw HTML and contractor/contact payloads are never kept.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import html
import json
import re
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests


SOURCE = "PL_BZP"
COUNTRY = "POL"
BZP_API = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
BZP_STATS = f"{BZP_API}/stats"
BZP_HUMAN = "https://ezamowienia.gov.pl/mo-client-board/bzp/notice-details/id/{object_id}"
BZP_ATTRIBUTION = "Biuletyn Zamówień Publicznych (BZP) — Platforma e-Zamówienia"
BZP_DATASET = "Biuletyn Zamówień Publicznych — e-Zamówienia"
BZP_INTEGRATION_INFO = "https://ezamowienia.gov.pl/pl/integracja-z-systemem/"
BZP_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal BZP connector/1.0 (+official public-data ingestion)",
}
WARSAW = ZoneInfo("Europe/Warsaw")
NOTICE_TYPES = ("ContractNotice", "NoticeUpdateNotice", "TenderResultNotice")


def _text(value):
    return "" if value is None else str(value).strip()


def _dt(value):
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


def _utc(value):
    parsed = _dt(value)
    if parsed is None:
        return None
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _query_stamp(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _human_url(object_id):
    value = _text(object_id)
    return BZP_HUMAN.format(object_id=quote(value, safe="")) if value else ""


class _PartsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        value = " ".join(str(data).split())
        if value:
            self.parts.append(html.unescape(value))


def _html_parts(value):
    parser = _PartsParser()
    parser.feed(str(value or ""))
    return parser.parts


def parse_bzp_update_deadline(html_body):
    """Return the final corrected UTC deadline or None when 8.1 is untouched.

    Live BZP validation on 2026-08-24 observed the exact sequence:
    ``8.1. Termin składania ofert`` / ``Przed zmianą:`` / old value /
    ``Po zmianie:`` / new ``YYYY-MM-DD HH:MM`` value. If BZP says section 8.1
    changed but this exact structure cannot be parsed, fail closed.
    """
    parts = _html_parts(html_body)
    headings = [i for i, part in enumerate(parts) if "8.1. Termin składania ofert" in part]
    if not headings:
        return None
    values = []
    for index in headings:
        tail = parts[index + 1:index + 6]
        if len(tail) < 4 or tail[0] != "Przed zmianą:" or tail[2] != "Po zmianie:":
            raise RuntimeError("BZP deadline update section 8.1 has unsupported structure; cursor not advanced")
        try:
            datetime.strptime(tail[1], "%Y-%m-%d %H:%M")
            local_new = datetime.strptime(tail[3], "%Y-%m-%d %H:%M").replace(tzinfo=WARSAW)
        except ValueError as exc:
            raise RuntimeError("BZP deadline update section 8.1 has invalid date value; cursor not advanced") from exc
        values.append(local_new.astimezone(timezone.utc))
    return _utc(values[-1])


def parse_bzp_cpvs(value):
    """Parse publisher CPV text without translating or inventing codes."""
    text = _text(value)
    if not text:
        return []
    matches = list(re.finditer(r"\b\d{8}-\d\b", text))
    entries, seen = [], set()
    for index, match in enumerate(matches):
        code = match.group(0)
        if code in seen:
            continue
        seen.add(code)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        description = text[match.end():end].strip(" \t\r\n,()")
        entries.append({"id": code, "description": description})
    return entries


def _place(row):
    values = []
    for key in ("organizationCity", "organizationProvince", "organizationCountry"):
        value = _text(row.get(key))
        if value and value not in values:
            values.append(value)
    return " | ".join(values)


def _state_from_contract(row, *, was_actionable=False):
    if _text(row.get("orderType")) != "Works":
        return None
    tender_id = _text(row.get("tenderId"))
    object_id = _text(row.get("objectId"))
    published = _utc(row.get("publicationDate"))
    if not tender_id or not object_id or not published:
        raise RuntimeError("BZP Works ContractNotice missing tenderId/objectId/publicationDate; cursor not advanced")
    return {
        "tender_id": tender_id,
        "title": _text(row.get("orderObject")),
        "buyer": _text(row.get("organizationName")),
        "place": _place(row),
        "cpv_classifications": parse_bzp_cpvs(row.get("cpvCode")),
        "deadline": _utc(row.get("submittingOffersDate")) or "",
        "first_published_at": published,
        "source_updated_at": published,
        "object_id": object_id,
        "notice_number": _text(row.get("noticeNumber")),
        "bzp_number": _text(row.get("bzpNumber")),
        "tender_type": _text(row.get("tenderType")),
        "last_notice_type": "ContractNotice",
        "was_actionable": bool(was_actionable),
    }


def _refresh_state_from_notice(state, row, notice_type):
    if _text(row.get("orderObject")):
        state["title"] = _text(row.get("orderObject"))
    cpvs = parse_bzp_cpvs(row.get("cpvCode"))
    if cpvs:
        state["cpv_classifications"] = cpvs
    state["object_id"] = _text(row.get("objectId")) or state.get("object_id")
    state["notice_number"] = _text(row.get("noticeNumber")) or state.get("notice_number")
    state["bzp_number"] = _text(row.get("bzpNumber")) or state.get("bzp_number")
    state["source_updated_at"] = _utc(row.get("publicationDate")) or state.get("source_updated_at")
    state["last_notice_type"] = notice_type
    return state


def _observation(state, *, now, actionable=None, lifecycle_status=None, lifecycle_reason=None, lifecycle_only=False):
    tender_id = _text(state.get("tender_id"))
    cpvs = [entry for entry in state.get("cpv_classifications", []) if isinstance(entry, dict) and _text(entry.get("id"))]
    primary = _text(cpvs[0].get("id")) if cpvs else ""
    deadline = _utc(state.get("deadline")) or ""
    current = _dt(now) or datetime.now(timezone.utc)
    deadline_dt = _dt(deadline)
    if actionable is None:
        actionable = bool(deadline_dt and deadline_dt > current)
        lifecycle_status = "active" if actionable else ("deadline_missing" if deadline_dt is None else "deadline_elapsed")
        lifecycle_reason = (
            "publisher reports Works ContractNotice with future submission deadline"
            if actionable else
            ("Works notice has no valid submission deadline" if deadline_dt is None else "submission deadline has elapsed")
        )
    record = {
        "source": SOURCE,
        "external_id": tender_id,
        "title": _text(state.get("title")),
        "description": _text(state.get("title")),
        "buyer": _text(state.get("buyer")),
        "country": COUNTRY,
        "cpv": primary,
        "taxonomy": "CPV" if primary else "",
        "category_code": primary,
        "cpv_codes": [_text(entry.get("id")) for entry in cpvs],
        "cpv_classifications": cpvs,
        "value": "",
        "currency": "",
        "deadline": deadline,
        "publication_date": _text(state.get("first_published_at"))[:10],
        "published_at": _text(state.get("first_published_at")) or None,
        "source_updated_at": _text(state.get("source_updated_at")) or None,
        "url": _human_url(state.get("object_id")),
        "market": "GLOBAL",
        "place": _text(state.get("place")),
        "source_status": _text(state.get("last_notice_type")),
        "source_phase": _text(state.get("last_notice_type")),
        "signal_type": "TENDER",
        "procurement_method": _text(state.get("tender_type")),
        "contract_type": "works",
        "source_reference": _text(state.get("object_id")),
        "notice_identifier": _text(state.get("notice_number")),
        "bzp_number": _text(state.get("bzp_number")),
        "ocid": tender_id,
        "attribution": BZP_ATTRIBUTION,
        "source_dataset": BZP_DATASET,
        "source_api_url": BZP_API,
        "reuse_information": BZP_INTEGRATION_INFO,
        "source_modified": True,
        "is_actionable": bool(actionable),
        "lifecycle_status": lifecycle_status or ("active" if actionable else "inactive"),
        "lifecycle_reason": lifecycle_reason or "publisher lifecycle state",
    }
    if lifecycle_only or not actionable:
        record["_lifecycle_only"] = True
    return record


def _result_status(value):
    tokens = [token.strip().lower() for token in _text(value).split(";") if token.strip()]
    if tokens and all(token == "uniewaznienie" for token in tokens):
        return "cancelled", "BZP TenderResultNotice reports procedure cancellation"
    if "zawarcieumowy" in tokens:
        return "contract_concluded", "BZP TenderResultNotice reports contract conclusion/result publication"
    return "result_published", "BZP TenderResultNotice closes the submission opportunity"


@dataclass
class BZPCursor:
    completed_through: str
    tracked: dict
    closed: dict

    def encode(self):
        return json.dumps(
            {
                "completed_through": self.completed_through,
                "tracked": self.tracked,
                "closed": self.closed,
            },
            ensure_ascii=False,
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
            except json.JSONDecodeError as exc:
                raise RuntimeError("invalid PL_BZP cursor JSON") from exc
            stamp = _text(payload.get("completed_through"))
            tracked = payload.get("tracked") or {}
            closed = payload.get("closed") or {}
            if not isinstance(tracked, dict) or not isinstance(closed, dict):
                raise RuntimeError("invalid PL_BZP cursor procedure state")
        else:
            stamp, tracked, closed = text, {}, {}
        if _dt(stamp) is None:
            raise RuntimeError("invalid PL_BZP cursor completed_through")
        return cls(_utc(stamp), tracked, closed)


class PolandBZPConnector:
    def __init__(
        self,
        *,
        session=None,
        max_page_size=250,
        initial_lookback_days=30,
        overlap_minutes=5,
        max_window_days=1,
        max_windows_per_sync=31,
        max_split_depth=12,
        max_requests_per_sync=260,
        timeout=60,
    ):
        self.session = session or requests.Session()
        self.max_page_size = max(1, int(max_page_size))
        self.initial_lookback_days = max(1, int(initial_lookback_days))
        self.overlap_minutes = max(0, int(overlap_minutes))
        self.max_window_days = max(1, int(max_window_days))
        self.max_windows_per_sync = max(1, int(max_windows_per_sync))
        self.max_split_depth = max(1, int(max_split_depth))
        self.max_requests_per_sync = max(1, int(max_requests_per_sync))
        self.timeout = int(timeout)
        self._requests = 0

    def _get(self, url, *, params):
        self._requests += 1
        if self._requests > self.max_requests_per_sync:
            raise RuntimeError(f"PL_BZP exceeded max_requests_per_sync={self.max_requests_per_sync}; cursor not advanced")
        response = self.session.get(url, params=params, headers=BZP_HEADERS, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _stats(self, start, end):
        payload = self._get(
            BZP_STATS,
            params={"PublicationDateFrom": _query_stamp(start), "PublicationDateTo": _query_stamp(end)},
        )
        if not isinstance(payload, list):
            raise RuntimeError("PL_BZP stats response is not a list; cursor not advanced")
        counts = {notice_type: 0 for notice_type in NOTICE_TYPES}
        for row in payload:
            if not isinstance(row, dict):
                continue
            notice_type = _text(row.get("noticeType"))
            if notice_type not in counts:
                continue
            try:
                counts[notice_type] += int(row.get("numberOfNotices") or 0)
            except (TypeError, ValueError) as exc:
                raise RuntimeError("PL_BZP stats contains invalid count; cursor not advanced") from exc
        return counts

    def _list(self, notice_type, start, end, expected):
        if expected <= 0:
            return []
        payload = self._get(
            BZP_API,
            params={
                "NoticeType": notice_type,
                "PublicationDateFrom": _query_stamp(start),
                "PublicationDateTo": _query_stamp(end),
                "PageSize": expected,
            },
        )
        if not isinstance(payload, list):
            raise RuntimeError(f"PL_BZP {notice_type} response is not a list; cursor not advanced")
        rows = [row for row in payload if isinstance(row, dict)]
        if len(rows) != expected:
            raise RuntimeError(
                f"PL_BZP {notice_type} stats/list mismatch expected={expected} returned={len(rows)}; cursor not advanced"
            )
        object_ids = [_text(row.get("objectId")) for row in rows]
        if any(not value for value in object_ids) or len(set(object_ids)) != expected:
            raise RuntimeError(f"PL_BZP {notice_type} returned missing/duplicate objectId; cursor not advanced")
        return rows

    def _fetch_interval(self, start, end, *, depth=0):
        counts = self._stats(start, end)
        if any(count > self.max_page_size for count in counts.values()):
            if depth >= self.max_split_depth or (end - start) <= timedelta(seconds=1):
                raise RuntimeError("PL_BZP interval cannot be split to complete page; cursor not advanced")
            midpoint = start + (end - start) / 2
            merged = {}
            for row in self._fetch_interval(start, midpoint, depth=depth + 1) + self._fetch_interval(midpoint, end, depth=depth + 1):
                object_id = _text(row.get("objectId"))
                if object_id:
                    merged[object_id] = row
            return list(merged.values())
        rows = []
        for notice_type in NOTICE_TYPES:
            rows.extend(self._list(notice_type, start, end, counts[notice_type]))
        return rows

    def _windows(self, start, end):
        current, count = start, 0
        width = timedelta(days=self.max_window_days)
        while current < end and count < self.max_windows_per_sync:
            boundary = min(end, current + width)
            yield current, boundary
            current, count = boundary, count + 1

    @staticmethod
    def _event_key(row):
        published = _dt(row.get("publicationDate")) if isinstance(row, dict) else None
        return (published or datetime.min.replace(tzinfo=timezone.utc), _text(row.get("objectId")))

    def _process_events(self, rows, tracked, closed):
        seen_objects = set()
        for row in sorted((row for row in rows if isinstance(row, dict)), key=self._event_key):
            object_id = _text(row.get("objectId"))
            if object_id in seen_objects:
                continue
            seen_objects.add(object_id)
            notice_type = _text(row.get("noticeType"))
            tender_id = _text(row.get("tenderId"))

            if notice_type == "ContractNotice":
                if _text(row.get("orderType")) != "Works":
                    if tender_id and tender_id in tracked:
                        state = _refresh_state_from_notice(tracked.pop(tender_id), row, notice_type)
                        state["closed_status"] = "not_construction"
                        state["closed_reason"] = "publisher ContractNotice no longer reports orderType=Works"
                        closed[tender_id] = state
                    continue
                previous = tracked.get(tender_id) if tender_id else None
                state = _state_from_contract(row, was_actionable=bool(previous and previous.get("was_actionable")))
                tender_id = state["tender_id"]
                tracked[tender_id] = state
                closed.pop(tender_id, None)
                continue

            if notice_type == "NoticeUpdateNotice":
                if not tender_id or tender_id not in tracked:
                    continue
                state = tracked[tender_id]
                corrected_deadline = parse_bzp_update_deadline(row.get("htmlBody"))
                if corrected_deadline:
                    state["deadline"] = corrected_deadline
                _refresh_state_from_notice(state, row, notice_type)
                continue

            if notice_type == "TenderResultNotice":
                if not tender_id or tender_id not in tracked:
                    continue
                state = _refresh_state_from_notice(tracked.pop(tender_id), row, notice_type)
                status, reason = _result_status(row.get("procedureResult"))
                state["closed_status"] = status
                state["closed_reason"] = reason
                closed[tender_id] = state

    def _finalize(self, tracked, closed, *, now):
        observations = []
        survivors = {}
        for tender_id, state in closed.items():
            if state.get("was_actionable"):
                observations.append(_observation(
                    state,
                    now=now,
                    actionable=False,
                    lifecycle_status=_text(state.get("closed_status")) or "result_published",
                    lifecycle_reason=_text(state.get("closed_reason")) or "publisher reports closed procedure",
                    lifecycle_only=True,
                ))
        for tender_id, state in tracked.items():
            deadline = _dt(state.get("deadline"))
            if deadline is not None and deadline > now:
                state["was_actionable"] = True
                survivors[tender_id] = state
                observations.append(_observation(
                    state,
                    now=now,
                    actionable=True,
                    lifecycle_status="active",
                    lifecycle_reason="publisher reports Works procedure with future submission deadline",
                ))
                continue

            if deadline is None:
                # Keep a source-native Works procedure pending even when its summary
                # has no deadline. A later NoticeUpdateNotice may supply section 8.1;
                # discarding it here would lose the construction provenance needed
                # to apply that update safely.
                if state.get("was_actionable"):
                    observations.append(_observation(
                        state,
                        now=now,
                        actionable=False,
                        lifecycle_status="deadline_missing",
                        lifecycle_reason="Works procedure no longer has a valid submission deadline",
                        lifecycle_only=True,
                    ))
                    state["was_actionable"] = False
                survivors[tender_id] = state
                continue

            if state.get("was_actionable"):
                observations.append(_observation(
                    state,
                    now=now,
                    actionable=False,
                    lifecycle_status="deadline_elapsed",
                    lifecycle_reason="submission deadline has elapsed",
                    lifecycle_only=True,
                ))
        return observations, survivors

    def fetch_incremental(self, *, watermark=None, now=None):
        self._requests = 0
        current = _dt(now) or datetime.now(timezone.utc)
        cursor = BZPCursor.decode(watermark) if watermark else None
        tracked = json.loads(json.dumps(cursor.tracked, ensure_ascii=False)) if cursor else {}
        closed = json.loads(json.dumps(cursor.closed, ensure_ascii=False)) if cursor else {}
        if cursor:
            # Preserve the publisher state exactly as persisted. In particular,
            # an incomplete historical catch-up may contain Works procedures that
            # were never emitted to users and therefore must remain
            # ``was_actionable=False`` rather than turning into fake tombstones.
            start = _dt(cursor.completed_through) - timedelta(minutes=self.overlap_minutes)
        else:
            start = current - timedelta(days=self.initial_lookback_days)

        completed = _dt(cursor.completed_through) if cursor else None
        any_window = False
        for window_start, window_end in self._windows(start, current):
            any_window = True
            rows = self._fetch_interval(window_start, window_end)
            self._process_events(rows, tracked, closed)
            completed = window_end
        if not any_window:
            completed = current
        if completed is None:
            completed = current

        caught_up = completed >= current
        if caught_up:
            observations, tracked = self._finalize(tracked, closed, now=current)
            closed = {}
        else:
            # Never publish an intermediate state while a long-outage catch-up is
            # incomplete: later updates/results may change what is currently true.
            observations = []

        next_cursor = BZPCursor(_utc(completed), tracked, closed).encode()
        return observations, next_cursor


def build_poland_bzp_connector(*, session=None, **kwargs):
    return PolandBZPConnector(session=session, **kwargs)


def fetch_poland_bzp_tenders(*, watermark=None, now=None, connector=None):
    client = connector or build_poland_bzp_connector()
    return client.fetch_incremental(watermark=watermark, now=now)