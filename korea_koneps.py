"""South Korea PPS KONEPS construction-bid connector.

The supported source is the official Public Data Portal API published by the
Public Procurement Service (PPS): ``BidPublicInfoService`` operation
``getBidPblancListInfoCnstwk``. That operation is construction-specific, so
ObraSignal never infers Works from titles or keywords.

Production access requires a data.go.kr service key. The connector is therefore
implemented and testable, but the registry remains credential-blocked until a
real key is supplied and live validation succeeds.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import os
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import requests


SOURCE = "KR_KONEPS"
COUNTRY = "KOR"
KONEPS_API = (
    "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/"
    "getBidPblancListInfoCnstwk"
)
KONEPS_DATASET_URL = "https://www.data.go.kr/data/15129394/openapi.do"
KONEPS_ATTRIBUTION = "Public Procurement Service (PPS) — KONEPS / 나라장터"
KONEPS_DATASET = "나라장터 입찰공고정보서비스 — 공사"
SEOUL = ZoneInfo("Asia/Seoul")


def _text(value):
    return "" if value is None else " ".join(str(value).split())


def _service_key(value=None):
    raw = _text(value) or _text(os.getenv("OBRASIGNAL_KR_KONEPS_SERVICE_KEY"))
    if not raw:
        raise RuntimeError(
            "KR_KONEPS requires OBRASIGNAL_KR_KONEPS_SERVICE_KEY; "
            "obtain an approved service key for PPS BidPublicInfoService"
        )
    # data.go.kr exposes both encoded and decoded representations. requests will
    # encode query parameters itself, so normalize a copied encoded key first.
    return unquote(raw) if "%" in raw else raw


def _parse_kst(value):
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _text(value)
        if not text:
            return None
        parsed = None
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y%m%d%H%M%S",
            "%Y%m%d%H%M",
        ):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                pass
        if parsed is None:
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SEOUL)
    return parsed.astimezone(timezone.utc)


def _utc(value):
    parsed = _parse_kst(value)
    return None if parsed is None else parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _day(value, *, label="day"):
    try:
        return date.fromisoformat(_text(value))
    except ValueError as exc:
        raise RuntimeError(f"invalid {SOURCE} cursor {label}") from exc


def _order(value):
    text = _text(value)
    try:
        return int(text)
    except ValueError:
        return -1


def _cancelled(kind):
    value = _text(kind).casefold()
    return "취소" in value or "cancel" in value


def _version_key(state):
    changed = _parse_kst(state.get("source_updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
    return (
        changed,
        _order(state.get("notice_order")),
        _text(state.get("source_status")),
    )


def _documents(row):
    out = []
    for i in range(1, 11):
        url = _text(row.get(f"ntceSpecDocUrl{i}"))
        name = _text(row.get(f"ntceSpecFileNm{i}"))
        if url:
            item = {"url": url, "name": name}
            if item not in out:
                out.append(item)
    std = _text(row.get("stdNtceDocUrl"))
    if std and all(item["url"] != std for item in out):
        out.append({"url": std, "name": ""})
    return out


def _event(row, *, query_day, query_div):
    if not isinstance(row, dict):
        raise RuntimeError(f"{SOURCE} API returned non-object item; cursor not advanced")

    notice_no = _text(row.get("bidNtceNo"))
    notice_order = _text(row.get("bidNtceOrd"))
    title = _text(row.get("bidNtceNm"))
    source_updated_at = _utc(row.get("chgDt") or row.get("rgstDt") or row.get("bidNtceDt"))
    first_published_at = _utc(row.get("bidNtceDt") or row.get("rgstDt"))

    if not notice_no or not notice_order or not source_updated_at:
        raise RuntimeError(
            f"{SOURCE} construction row missing bidNtceNo/bidNtceOrd/change timestamp; cursor not advanced"
        )

    amount = _text(row.get("presmptPrce")) or _text(row.get("bdgtAmt"))
    return {
        "external_id": notice_no,
        "notice_no": notice_no,
        "notice_order": notice_order,
        "source_status": _text(row.get("ntceKindNm")),
        "source_updated_at": source_updated_at,
        "first_published_at": first_published_at or source_updated_at,
        "query_day": query_day,
        "query_div": str(query_div),
        "title": title or notice_no,
        "description": title or notice_no,
        "buyer": _text(row.get("ntceInsttNm")),
        "demand_org": _text(row.get("dminsttNm")),
        "buyer_contact_name": _text(row.get("ntceInsttOfclNm")),
        "buyer_contact_phone": _text(row.get("ntceInsttOfclTelNo")),
        "buyer_contact_email": _text(row.get("ntceInsttOfclEmailAdrs")),
        "deadline": _utc(row.get("bidClseDt")) or "",
        "bid_begin": _utc(row.get("bidBeginDt")) or "",
        "opening_at": _utc(row.get("opengDt")) or "",
        "value": amount,
        "currency": "KRW" if amount else "",
        "place": _text(row.get("cnstrtsiteRgnNm")),
        "bid_method": _text(row.get("bidMethdNm")),
        "contract_method": _text(row.get("cntrctCnclsMthdNm")),
        "award_method": _text(row.get("sucsfbidMthdNm")),
        "detail_url": _text(row.get("bidNtceDtlUrl")),
        "documents": _documents(row),
        "registration_type": _text(row.get("rgstTyNm")),
        "reannouncement": _text(row.get("reNtceYn")).upper() == "Y",
        "change_reason": _text(row.get("chgNtceRsn")),
        "cancelled": _cancelled(row.get("ntceKindNm")),
        "was_visible": False,
    }


def _merge_state(current, incoming):
    if current is None:
        return deepcopy(incoming)
    if _version_key(incoming) <= _version_key(current):
        return current
    updated = deepcopy(incoming)
    updated["was_visible"] = bool(current.get("was_visible")) or bool(incoming.get("was_visible"))
    first = [
        _text(v)
        for v in (current.get("first_published_at"), incoming.get("first_published_at"))
        if _text(v)
    ]
    if first:
        updated["first_published_at"] = min(first)
    return updated


def _observation(state, *, actionable, lifecycle_status, lifecycle_reason, lifecycle_only=False):
    documents = [item for item in state.get("documents", []) if isinstance(item, dict)]
    detail_url = _text(state.get("detail_url"))
    if not detail_url:
        notice_no = _text(state.get("notice_no"))
        notice_order = _text(state.get("notice_order"))
        if notice_no:
            detail_url = (
                "https://www.g2b.go.kr/link/PNPE027_01/single/"
                f"?bidPbancNo={notice_no}&bidPbancOrd={notice_order or '000'}"
            )
    row = {
        "source": SOURCE,
        "external_id": _text(state.get("external_id")),
        "title": _text(state.get("title")),
        "description": _text(state.get("description")),
        "buyer": _text(state.get("buyer")),
        "country": COUNTRY,
        "cpv": "",
        "taxonomy": "",
        "category_code": "",
        "cpv_codes": [],
        "value": _text(state.get("value")),
        "currency": _text(state.get("currency")),
        "deadline": _text(state.get("deadline")),
        "publication_date": _text(state.get("first_published_at"))[:10],
        "published_at": _text(state.get("first_published_at")) or None,
        "source_updated_at": _text(state.get("source_updated_at")) or None,
        "url": detail_url,
        "market": "GLOBAL",
        "place": _text(state.get("place")),
        "source_status": _text(state.get("source_status")),
        "source_phase": "BID_NOTICE",
        "signal_type": "TENDER",
        "procurement_method": " | ".join(
            part for part in (_text(state.get("bid_method")), _text(state.get("contract_method"))) if part
        ),
        "contract_type": "works",
        "source_reference": _text(state.get("notice_no")),
        "notice_identifier": _text(state.get("notice_no")),
        "koneps_bid_notice_no": _text(state.get("notice_no")),
        "koneps_bid_notice_order": _text(state.get("notice_order")),
        "koneps_demand_org": _text(state.get("demand_org")),
        "koneps_award_method": _text(state.get("award_method")),
        "koneps_registration_type": _text(state.get("registration_type")),
        "koneps_reannouncement": bool(state.get("reannouncement")),
        "koneps_change_reason": _text(state.get("change_reason")),
        "koneps_bid_begin": _text(state.get("bid_begin")),
        "koneps_opening_at": _text(state.get("opening_at")),
        "koneps_documents": documents,
        "buyer_contact_name": _text(state.get("buyer_contact_name")),
        "buyer_contact_phone": _text(state.get("buyer_contact_phone")),
        "buyer_contact_email": _text(state.get("buyer_contact_email")),
        "attribution": KONEPS_ATTRIBUTION,
        "source_dataset": KONEPS_DATASET,
        "source_api_url": KONEPS_API,
        "reuse_information": KONEPS_DATASET_URL,
        "source_modified": True,
        "is_actionable": bool(actionable),
        "lifecycle_status": lifecycle_status,
        "lifecycle_reason": lifecycle_reason,
    }
    if lifecycle_only or not actionable:
        row["_lifecycle_only"] = True
    return row


@dataclass
class KONEPSCursor:
    completed_through: str
    tracked: dict
    closed: dict

    def encode(self):
        return json.dumps(
            {"completed_through": self.completed_through, "tracked": self.tracked, "closed": self.closed},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def decode(cls, value):
        if not value:
            return None
        try:
            payload = json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"invalid {SOURCE} cursor JSON") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"invalid {SOURCE} cursor state")
        completed = _text(payload.get("completed_through"))
        tracked = payload.get("tracked") or {}
        closed = payload.get("closed") or {}
        _day(completed, label="completed_through")
        if not isinstance(tracked, dict) or not isinstance(closed, dict):
            raise RuntimeError(f"invalid {SOURCE} cursor state")
        return cls(completed, tracked, closed)


class KONEPSConstructionBidConnector:
    def __init__(
        self,
        *,
        service_key=None,
        session=None,
        initial_lookback_days=2,
        overlap_days=1,
        max_days_per_sync=3,
        page_size=100,
        max_pages_per_query=100,
        max_items_per_query=10000,
        timeout=60,
    ):
        self.service_key = _service_key(service_key)
        self.session = session or requests.Session()
        self.initial_lookback_days = max(1, int(initial_lookback_days))
        self.max_days_per_sync = max(1, int(max_days_per_sync))
        self.overlap_days = min(max(0, int(overlap_days)), max(0, self.max_days_per_sync - 1))
        self.page_size = max(1, min(1000, int(page_size)))
        self.max_pages_per_query = max(1, int(max_pages_per_query))
        self.max_items_per_query = max(self.page_size, int(max_items_per_query))
        self.timeout = max(1, int(timeout))

    @staticmethod
    def _target_day(now):
        current = _parse_kst(now) or datetime.now(timezone.utc)
        return current.astimezone(SEOUL).date()

    def _get_page(self, day, query_div, page_no):
        response = self.session.get(
            KONEPS_API,
            params={
                "serviceKey": self.service_key,
                "pageNo": int(page_no),
                "numOfRows": self.page_size,
                "type": "json",
                "inqryDiv": str(query_div),
                "inqryBgnDt": day.strftime("%Y%m%d0000"),
                "inqryEndDt": day.strftime("%Y%m%d2359"),
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{SOURCE} response is not valid JSON; cursor not advanced") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("response"), dict):
            raise RuntimeError(f"{SOURCE} response has unsupported schema; cursor not advanced")
        envelope = payload["response"]
        header = envelope.get("header")
        body = envelope.get("body")
        if not isinstance(header, dict) or not isinstance(body, dict):
            raise RuntimeError(f"{SOURCE} response header/body missing; cursor not advanced")
        if _text(header.get("resultCode")) != "00":
            raise RuntimeError(
                f"{SOURCE} API error code={_text(header.get('resultCode'))} "
                f"message={_text(header.get('resultMsg'))}; cursor not advanced"
            )
        items = body.get("items")
        if items in (None, ""):
            items = []
        if not isinstance(items, list):
            raise RuntimeError(f"{SOURCE} response items is not a list; cursor not advanced")
        try:
            total = int(body.get("totalCount") or 0)
            returned_page = int(body.get("pageNo") or page_no)
            returned_size = int(body.get("numOfRows") or self.page_size)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{SOURCE} pagination metadata invalid; cursor not advanced") from exc
        if total < 0 or returned_page != int(page_no) or returned_size <= 0:
            raise RuntimeError(f"{SOURCE} pagination metadata inconsistent; cursor not advanced")
        pages = 0 if total == 0 else (total + returned_size - 1) // returned_size
        if pages > self.max_pages_per_query or total > self.max_items_per_query:
            raise RuntimeError(f"{SOURCE} daily query exceeds configured hard limits; cursor not advanced")
        return items, total, pages

    def _fetch_query(self, day, query_div):
        first_items, total, pages = self._get_page(day, query_div, 1)
        if total == 0:
            if first_items:
                raise RuntimeError(f"{SOURCE} empty-count metadata mismatch; cursor not advanced")
            return []
        rows = []
        for page_no in range(1, pages + 1):
            if page_no == 1:
                items, page_total, page_count = first_items, total, pages
            else:
                items, page_total, page_count = self._get_page(day, query_div, page_no)
            if page_total != total or page_count != pages:
                raise RuntimeError(f"{SOURCE} pagination changed during query; cursor not advanced")
            for item in items:
                if not isinstance(item, dict):
                    raise RuntimeError(f"{SOURCE} API returned non-object item; cursor not advanced")
                rows.append(item)
        if len(rows) != total:
            raise RuntimeError(
                f"{SOURCE} pagination count mismatch expected={total} returned={len(rows)}; cursor not advanced"
            )
        return rows

    def _fetch_day(self, day):
        merged = []
        seen = {}
        # 1 = registration time, 3 = change time. Reading both prevents a new
        # notice and a later change/cancellation from falling into different blind spots.
        for query_div in (1, 3):
            for row in self._fetch_query(day, query_div):
                event = _event(row, query_day=day.isoformat(), query_div=query_div)
                key = (
                    event["notice_no"],
                    event["notice_order"],
                    event["source_updated_at"],
                    event["source_status"],
                )
                fingerprint = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
                if key in seen:
                    if seen[key] != fingerprint:
                        raise RuntimeError(
                            f"{SOURCE} returned conflicting payloads for one notice version; cursor not advanced"
                        )
                    continue
                seen[key] = fingerprint
                merged.append(event)
        return merged

    @staticmethod
    def _apply_events(events, tracked, closed):
        for event in sorted(events, key=_version_key):
            external_id = _text(event.get("external_id"))
            if not external_id:
                raise RuntimeError(f"{SOURCE} event missing bid identity; cursor not advanced")
            current = tracked.get(external_id) or closed.get(external_id)
            if current is not None and _version_key(event) <= _version_key(current):
                continue
            if event.get("cancelled"):
                if current is None:
                    continue
                state = _merge_state(current, event)
                state["closed_status"] = "publisher_cancelled"
                state["closed_reason"] = "latest KONEPS construction notice is a cancellation notice"
                tracked.pop(external_id, None)
                closed[external_id] = state
                continue
            tracked[external_id] = _merge_state(current, event)
            closed.pop(external_id, None)

    @staticmethod
    def _finalize(tracked, closed, *, now):
        observations, survivors = [], {}
        current = _parse_kst(now) or datetime.now(timezone.utc)

        for state in closed.values():
            if state.get("was_visible"):
                observations.append(_observation(
                    state,
                    actionable=False,
                    lifecycle_status=_text(state.get("closed_status")) or "publisher_cancelled",
                    lifecycle_reason=_text(state.get("closed_reason")) or "KONEPS notice is no longer actionable",
                    lifecycle_only=True,
                ))

        for external_id, state in tracked.items():
            deadline = _parse_kst(state.get("deadline"))
            if deadline is not None and deadline > current:
                state["was_visible"] = True
                survivors[external_id] = state
                observations.append(_observation(
                    state,
                    actionable=True,
                    lifecycle_status="active",
                    lifecycle_reason="KONEPS construction notice has a future structured bid deadline",
                ))
                continue
            if deadline is None:
                if state.get("was_visible"):
                    observations.append(_observation(
                        state,
                        actionable=False,
                        lifecycle_status="deadline_missing",
                        lifecycle_reason="latest KONEPS notice no longer has a valid structured bid deadline",
                        lifecycle_only=True,
                    ))
                    state["was_visible"] = False
                survivors[external_id] = state
                continue
            if state.get("was_visible"):
                observations.append(_observation(
                    state,
                    actionable=False,
                    lifecycle_status="deadline_elapsed",
                    lifecycle_reason="KONEPS bid deadline has elapsed",
                    lifecycle_only=True,
                ))
        return observations, survivors

    def fetch_incremental(self, *, watermark=None, now=None):
        current = _parse_kst(now) or datetime.now(timezone.utc)
        target = self._target_day(current)
        cursor = KONEPSCursor.decode(watermark) if watermark else None
        tracked = deepcopy(cursor.tracked) if cursor else {}
        closed = deepcopy(cursor.closed) if cursor else {}

        if cursor:
            completed = _day(cursor.completed_through, label="completed_through")
            if completed > target:
                raise RuntimeError(f"{SOURCE} cursor is ahead of current Seoul day; cursor not advanced")
            start = completed + timedelta(days=1) - timedelta(days=self.overlap_days)
        else:
            completed = target - timedelta(days=self.initial_lookback_days)
            start = completed + timedelta(days=1)

        days = []
        day = start
        while day <= target and len(days) < self.max_days_per_sync:
            days.append(day)
            day += timedelta(days=1)

        for query_day in days:
            self._apply_events(self._fetch_day(query_day), tracked, closed)
            if query_day > completed:
                completed = query_day

        if completed >= target:
            observations, tracked = self._finalize(tracked, closed, now=current)
            closed = {}
        else:
            observations = []

        return observations, KONEPSCursor(completed.isoformat(), tracked, closed).encode()


def build_korea_koneps_connector(*, session=None, service_key=None, **kwargs):
    return KONEPSConstructionBidConnector(session=session, service_key=service_key, **kwargs)


def fetch_korea_koneps_tenders(*, watermark=None, now=None, connector=None):
    client = connector or build_korea_koneps_connector()
    return client.fetch_incremental(watermark=watermark, now=now)
