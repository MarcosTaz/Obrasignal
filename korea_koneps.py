"""Credential-gated Korea PPS/KONEPS construction bid notice connector.

Implements the documented Public Data Portal construction operation
``getBidPblancListInfoCnstwk`` without changing ObraSignal's production gate.
The operation itself is publisher-native ``공사`` (Works), so construction is
never inferred from titles or keywords.

A valid Public Data Portal service key is mandatory. Until an authorized key is
available and live validation passes, ``KR_KONEPS`` remains planned and this
module is deliberately not wired into runtime.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
import os
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import requests


SOURCE = "KR_KONEPS"
COUNTRY = "KOR"
KONEPS_BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"
KONEPS_CONSTRUCTION_ENDPOINT = f"{KONEPS_BASE}/getBidPblancListInfoCnstwk"
KONEPS_ATTRIBUTION = "Public Procurement Service (PPS) — KONEPS / 나라장터"
KONEPS_DATASET = "조달청_나라장터 입찰공고정보서비스 — 공사"
SEOUL = ZoneInfo("Asia/Seoul")
_ACTIVE_NOTICE_KINDS = frozenset(("등록공고", "변경공고", "재공고"))
_CANCELLED_NOTICE_KIND = "취소공고"


def _text(value):
    return "" if value is None else " ".join(str(value).split())


def _normalize_service_key(value):
    """Accept either the portal's encoded or decoded key without double-encoding."""
    text = _text(value)
    return unquote(text) if text else ""


def _source_dt(value):
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _text(value)
        if not text:
            return None
        parsed = None
        for candidate in (text, text.replace(" ", "T", 1)):
            try:
                parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
                break
            except ValueError:
                continue
        if parsed is None:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SEOUL)
    return parsed.astimezone(timezone.utc)


def _utc(value):
    parsed = _source_dt(value)
    return None if parsed is None else parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _floor_minute(value):
    parsed = _source_dt(value) or datetime.now(timezone.utc)
    return parsed.replace(second=0, microsecond=0)


def _query_dt(value):
    return value.astimezone(SEOUL).strftime("%Y%m%d%H%M")


def _cursor_dt(value, *, label="completed_through"):
    parsed = _source_dt(value)
    if parsed is None:
        raise RuntimeError(f"invalid {SOURCE} cursor {label}")
    return parsed.replace(second=0, microsecond=0)


def _identity(item):
    notice_no = _text(item.get("bidNtceNo"))
    notice_ord = _text(item.get("bidNtceOrd"))
    return f"{notice_no}:{notice_ord}" if notice_no and notice_ord else ""


def _event_key(state):
    updated = _source_dt(state.get("source_updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
    published = _source_dt(state.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc)
    return updated, published, _text(state.get("external_id"))


def _amount(item):
    for key in ("presmptPrce", "bdgtAmt", "mainCnsttyCnstwkPrearngAmt"):
        value = _text(item.get(key))
        if value:
            return value, key
    return "", ""


def _first_document(item):
    for index in range(1, 11):
        url = _text(item.get(f"ntceSpecDocUrl{index}"))
        if url:
            return url, _text(item.get(f"ntceSpecFileNm{index}"))
    return _text(item.get("stdNtceDocUrl")), ""


def _item_event(item):
    if not isinstance(item, dict):
        raise RuntimeError(f"{SOURCE} response contains non-object item; cursor not advanced")

    external_id = _identity(item)
    notice_no = _text(item.get("bidNtceNo"))
    notice_ord = _text(item.get("bidNtceOrd"))
    kind = _text(item.get("ntceKindNm"))
    # Incremental discovery is explicitly inqryDiv=3 (change datetime), so the
    # publisher's chgDt is part of the ordering contract. Falling back to a
    # registration/publication timestamp could advance past a change incorrectly.
    updated = _utc(item.get("chgDt"))
    if not external_id or not updated or not kind:
        raise RuntimeError(
            f"{SOURCE} construction item missing bidNtceNo/bidNtceOrd/ntceKindNm/chgDt change timestamp; cursor not advanced"
        )
    if kind not in _ACTIVE_NOTICE_KINDS and kind != _CANCELLED_NOTICE_KIND:
        raise RuntimeError(f"{SOURCE} construction item has unsupported ntceKindNm={kind!r}; cursor not advanced")

    value, value_source = _amount(item)
    document_url, document_name = _first_document(item)
    published = _utc(item.get("bidNtceDt") or item.get("rgstDt"))
    return {
        "external_id": external_id,
        "bid_notice_no": notice_no,
        "bid_notice_order": notice_ord,
        "procedure_id": _text(item.get("untyNtceNo")) or notice_no,
        "notice_kind": kind,
        "is_cancelled": kind == _CANCELLED_NOTICE_KIND,
        "source_updated_at": updated,
        "published_at": published,
        "first_published_at": published,
        "deadline": _utc(item.get("bidClseDt")) or "",
        "title": _text(item.get("bidNtceNm")) or external_id,
        "buyer": _text(item.get("dminsttNm")) or _text(item.get("ntceInsttNm")),
        "publishing_authority": _text(item.get("ntceInsttNm")),
        "place": _text(item.get("cnstrtsiteRgnNm")),
        "value": value,
        "value_source": value_source,
        "budget_amount": _text(item.get("bdgtAmt")),
        "estimated_price": _text(item.get("presmptPrce")),
        "main_work_type": _text(item.get("mainCnsttyNm")),
        "procurement_method": _text(item.get("cntrctCnclsMthdNm")) or _text(item.get("bidMethdNm")),
        "bid_method": _text(item.get("bidMethdNm")),
        "award_method": _text(item.get("sucsfbidMthdNm")),
        "change_reason": _text(item.get("chgNtceRsn")),
        "detail_url": _text(item.get("bidNtceDtlUrl")) or _text(item.get("bidNtceUrl")),
        "document_url": document_url,
        "document_name": document_name,
        "reference_no": _text(item.get("refNo")),
        "international_bid": _text(item.get("intrbidYn")),
        "reannouncement": _text(item.get("reNtceYn")),
        "was_visible": False,
    }


def _merge_state(current, incoming):
    if current is None:
        return deepcopy(incoming)
    if _event_key(incoming) <= _event_key(current):
        return current
    updated = deepcopy(incoming)
    updated["was_visible"] = bool(current.get("was_visible")) or bool(incoming.get("was_visible"))
    first_values = [
        value
        for value in (current.get("first_published_at"), incoming.get("first_published_at"))
        if _source_dt(value) is not None
    ]
    if first_values:
        updated["first_published_at"] = min(first_values, key=_source_dt)
    return updated


def _observation(state, *, actionable, lifecycle_status, lifecycle_reason, lifecycle_only=False):
    row = {
        "source": SOURCE,
        "external_id": _text(state.get("external_id")),
        "title": _text(state.get("title")),
        "description": _text(state.get("title")),
        "buyer": _text(state.get("buyer")),
        "country": COUNTRY,
        "cpv": "",
        "taxonomy": "",
        "category_code": "",
        "cpv_codes": [],
        "value": _text(state.get("value")),
        "currency": "KRW" if _text(state.get("value")) else "",
        "deadline": _text(state.get("deadline")),
        "publication_date": _text(state.get("first_published_at"))[:10],
        "published_at": _text(state.get("first_published_at")) or None,
        "source_updated_at": _text(state.get("source_updated_at")) or None,
        "url": _text(state.get("detail_url")),
        "market": "GLOBAL",
        "place": _text(state.get("place")),
        "source_status": _text(state.get("notice_kind")),
        "source_phase": "TENDER",
        "signal_type": "TENDER",
        "procurement_method": _text(state.get("procurement_method")),
        "contract_type": "works",
        "source_reference": _text(state.get("external_id")),
        "notice_identifier": _text(state.get("bid_notice_no")),
        "koneps_bid_notice_no": _text(state.get("bid_notice_no")),
        "koneps_bid_notice_order": _text(state.get("bid_notice_order")),
        "koneps_unified_notice_no": _text(state.get("procedure_id")),
        "koneps_main_work_type": _text(state.get("main_work_type")),
        "koneps_budget_amount": _text(state.get("budget_amount")),
        "koneps_estimated_price": _text(state.get("estimated_price")),
        "koneps_value_source": _text(state.get("value_source")),
        "koneps_bid_method": _text(state.get("bid_method")),
        "koneps_award_method": _text(state.get("award_method")),
        "koneps_change_reason": _text(state.get("change_reason")),
        "koneps_document_url": _text(state.get("document_url")),
        "koneps_document_name": _text(state.get("document_name")),
        "koneps_publishing_authority": _text(state.get("publishing_authority")),
        "koneps_reference_no": _text(state.get("reference_no")),
        "koneps_international_bid": _text(state.get("international_bid")),
        "koneps_reannouncement": _text(state.get("reannouncement")),
        "attribution": KONEPS_ATTRIBUTION,
        "source_dataset": KONEPS_DATASET,
        "source_api_url": KONEPS_CONSTRUCTION_ENDPOINT,
        "reuse_information": "https://www.data.go.kr/data/15129394/openapi.do",
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
        _cursor_dt(completed)
        if not isinstance(tracked, dict) or not isinstance(closed, dict):
            raise RuntimeError(f"invalid {SOURCE} cursor state")
        return cls(completed, tracked, closed)


class KONEPSConstructionConnector:
    def __init__(
        self,
        *,
        service_key=None,
        session=None,
        initial_lookback_minutes=60,
        overlap_minutes=5,
        max_minutes_per_sync=60,
        page_size=100,
        max_pages=100,
        max_items=10000,
        max_state_items=50000,
        timeout=45,
    ):
        raw_key = _text(service_key) or _text(os.getenv("KONEPS_SERVICE_KEY")) or _text(os.getenv("DATA_GO_KR_SERVICE_KEY"))
        self.service_key = _normalize_service_key(raw_key)
        self.session = session or requests.Session()
        self.initial_lookback_minutes = max(1, int(initial_lookback_minutes))
        self.overlap_minutes = max(0, int(overlap_minutes))
        self.max_minutes_per_sync = max(1, int(max_minutes_per_sync))
        self.page_size = max(1, min(1000, int(page_size)))
        self.max_pages = max(1, int(max_pages))
        self.max_items = max(self.page_size, int(max_items))
        self.max_state_items = max(1, int(max_state_items))
        self.timeout = max(1, int(timeout))

    def _require_service_key(self):
        if not self.service_key:
            raise RuntimeError(
                f"{SOURCE} requires an authorized Public Data Portal service key; set KONEPS_SERVICE_KEY"
            )

    def _get_page(self, start, end, page_no):
        self._require_service_key()
        try:
            response = self.session.get(
                KONEPS_CONSTRUCTION_ENDPOINT,
                params={
                    "serviceKey": self.service_key,
                    "pageNo": int(page_no),
                    "numOfRows": self.page_size,
                    "type": "json",
                    "inqryDiv": "3",
                    "inqryBgnDt": _query_dt(start),
                    "inqryEndDt": _query_dt(end),
                },
                headers={
                    "Accept": "application/json",
                    "User-Agent": "ObraSignal KONEPS connector/1.0 (+official public-data ingestion)",
                },
                timeout=self.timeout,
            )
        except Exception:
            raise RuntimeError(f"{SOURCE} network request failed; cursor not advanced") from None
        try:
            response.raise_for_status()
        except Exception:
            status = getattr(response, "status_code", "unknown")
            raise RuntimeError(f"{SOURCE} HTTP status {status}; cursor not advanced") from None

        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{SOURCE} response is not valid JSON; cursor not advanced") from exc
        envelope = payload.get("response") if isinstance(payload, dict) else None
        header = envelope.get("header") if isinstance(envelope, dict) else None
        body = envelope.get("body") if isinstance(envelope, dict) else None
        if not isinstance(header, dict) or not isinstance(body, dict):
            raise RuntimeError(f"{SOURCE} response has unsupported envelope; cursor not advanced")
        result_code = _text(header.get("resultCode"))
        if result_code != "00":
            # The publisher's diagnostic text is deliberately not propagated:
            # a remote error must never be able to echo the project service key.
            raise RuntimeError(
                f"{SOURCE} API rejected request resultCode={result_code!r}; cursor not advanced"
            )
        try:
            response_page = int(body.get("pageNo"))
            response_rows = int(body.get("numOfRows"))
            total_count = int(body.get("totalCount"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{SOURCE} pagination metadata is invalid; cursor not advanced") from exc
        if response_page != int(page_no) or response_rows <= 0 or total_count < 0:
            raise RuntimeError(f"{SOURCE} pagination metadata is inconsistent; cursor not advanced")

        items = body.get("items")
        if items is None:
            items = []
        elif isinstance(items, dict) and isinstance(items.get("item"), list):
            items = items["item"]
        elif isinstance(items, dict) and isinstance(items.get("item"), dict):
            items = [items["item"]]
        elif isinstance(items, dict) and _text(items.get("bidNtceNo")):
            items = [items]
        if not isinstance(items, list):
            raise RuntimeError(f"{SOURCE} items payload is unsupported; cursor not advanced")
        return items, total_count, response_rows

    def _fetch_window(self, start, end):
        first_items, total_count, response_rows = self._get_page(start, end, 1)
        if total_count > self.max_items:
            raise RuntimeError(f"{SOURCE} result exceeds configured item hard limit; cursor not advanced")
        pages = max(1, math.ceil(total_count / response_rows)) if total_count else 1
        if pages > self.max_pages:
            raise RuntimeError(f"{SOURCE} result exceeds configured page hard limit; cursor not advanced")

        rows = []
        seen = set()
        for page_no in range(1, pages + 1):
            if page_no == 1:
                items, page_total, page_rows = first_items, total_count, response_rows
            else:
                items, page_total, page_rows = self._get_page(start, end, page_no)
            if page_total != total_count or page_rows != response_rows:
                raise RuntimeError(f"{SOURCE} pagination changed during scan; cursor not advanced")
            for item in items:
                identity = _identity(item) if isinstance(item, dict) else ""
                if not identity:
                    raise RuntimeError(f"{SOURCE} construction item missing publisher identity; cursor not advanced")
                if identity in seen:
                    raise RuntimeError(f"{SOURCE} pagination returned duplicate bid identity; cursor not advanced")
                seen.add(identity)
                rows.append(item)
        if len(rows) != total_count:
            raise RuntimeError(
                f"{SOURCE} pagination count mismatch expected={total_count} returned={len(rows)}; cursor not advanced"
            )
        return rows

    @staticmethod
    def _apply_events(events, tracked, closed):
        for event in sorted(events, key=_event_key):
            external_id = _text(event.get("external_id"))
            current = tracked.get(external_id) or closed.get(external_id)
            if current is not None and _event_key(event) <= _event_key(current):
                continue
            if event.get("is_cancelled"):
                if current is None:
                    continue
                state = _merge_state(current, event)
                state["closed_status"] = "cancelled"
                state["closed_reason"] = _text(event.get("change_reason")) or "KONEPS reports 취소공고 (cancelled notice)"
                tracked.pop(external_id, None)
                closed[external_id] = state
                continue
            tracked[external_id] = _merge_state(current, event)
            closed.pop(external_id, None)

    def _check_state_limit(self, tracked, closed):
        if len(tracked) + len(closed) > self.max_state_items:
            raise RuntimeError(f"{SOURCE} cursor state exceeds configured hard limit; cursor not advanced")

    @staticmethod
    def _finalize(tracked, closed, *, now):
        observations = []
        survivors = {}
        current = _source_dt(now) or datetime.now(timezone.utc)

        for state in closed.values():
            if state.get("was_visible"):
                observations.append(_observation(
                    state,
                    actionable=False,
                    lifecycle_status=_text(state.get("closed_status")) or "cancelled",
                    lifecycle_reason=_text(state.get("closed_reason")) or "KONEPS notice is no longer actionable",
                    lifecycle_only=True,
                ))

        for external_id, state in tracked.items():
            deadline = _source_dt(state.get("deadline"))
            if deadline is not None and deadline > current:
                state["was_visible"] = True
                survivors[external_id] = state
                observations.append(_observation(
                    state,
                    actionable=True,
                    lifecycle_status="active",
                    lifecycle_reason="KONEPS construction notice has a future structured bid closing time",
                ))
                continue
            if deadline is None:
                if state.get("was_visible"):
                    observations.append(_observation(
                        state,
                        actionable=False,
                        lifecycle_status="deadline_missing",
                        lifecycle_reason="KONEPS construction notice no longer has a valid structured bid closing time",
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
                    lifecycle_reason="KONEPS bid closing time has elapsed",
                    lifecycle_only=True,
                ))
        return observations, survivors

    def fetch_incremental(self, *, watermark=None, now=None):
        self._require_service_key()
        current = _floor_minute(now)
        cursor = KONEPSCursor.decode(watermark) if watermark else None
        tracked = deepcopy(cursor.tracked) if cursor else {}
        closed = deepcopy(cursor.closed) if cursor else {}

        if cursor:
            completed = _cursor_dt(cursor.completed_through)
            if completed > current:
                raise RuntimeError(f"{SOURCE} cursor is ahead of current time; cursor not advanced")
            query_start = completed - timedelta(minutes=self.overlap_minutes)
            window_end = min(current, completed + timedelta(minutes=self.max_minutes_per_sync))
        else:
            completed = current - timedelta(minutes=self.initial_lookback_minutes)
            query_start = completed
            window_end = min(current, completed + timedelta(minutes=self.max_minutes_per_sync))

        events = [_item_event(item) for item in self._fetch_window(query_start, window_end)]
        self._apply_events(events, tracked, closed)
        self._check_state_limit(tracked, closed)
        completed = window_end

        if completed >= current:
            observations, tracked = self._finalize(tracked, closed, now=current)
            closed = {}
        else:
            observations = []

        return observations, KONEPSCursor(
            completed.isoformat(timespec="minutes").replace("+00:00", "Z"),
            tracked,
            closed,
        ).encode()


def build_korea_koneps_connector(*, service_key=None, session=None, **kwargs):
    return KONEPSConstructionConnector(service_key=service_key, session=session, **kwargs)


def fetch_korea_koneps_tenders(*, watermark=None, now=None, connector=None):
    client = connector or build_korea_koneps_connector()
    return client.fetch_incremental(watermark=watermark, now=now)
