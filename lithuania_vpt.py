"""Lithuania CVP IS public procurement snapshot connector.

Lithuania's Public Procurement Office (VPT) publishes a shared read API key and
an official POST export endpoint for CVP IS procurement data. The endpoint does
not expose a usable identity lookup and historical rows can change lifecycle
state in place without moving to the tail. Therefore this connector deliberately
uses a complete, bounded paginated snapshot instead of pretending tail paging is
an incremental cursor.

Production rules:
- scan the complete API snapshot at a proven page size of 2,000;
- fail closed on HTTP/JSON/page-integrity errors or duplicate/missing ids;
- publisher-native ``procurementType=Works`` is the construction gate;
- preliminary market consultations are excluded structurally by ``procedure``;
- only ``status=Bid submission`` with a valid future deadline is actionable;
- previous visible opportunities receive lifecycle-only tombstones when the
  source becomes terminal/inactive, the deadline expires, or the id disappears;
- cursor advancement happens only after the complete snapshot reconciles.

The API key below is not a secret: VPT publishes it verbatim in its official API
instructions for public data access.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import re
from zoneinfo import ZoneInfo

import requests


SOURCE = "LT_VPT"
COUNTRY = "LTU"
ENDPOINT = "https://viesiejipirkimai.lt/epps-integration/api/cft-details-export"
PUBLIC_API_KEY = "acec29bd-687c-4609-b211-c01b6cf51b55"
PUBLIC_SITE = "https://viesiejipirkimai.lt/epps/"
HUMAN_URL = "https://viesiejipirkimai.lt/epps/cft/prepareViewCfTWS.do?resourceId={resource_id}"
ATTRIBUTION = "Viešųjų pirkimų tarnyba (VPT), CVP IS"
VILNIUS = ZoneInfo("Europe/Vilnius")
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "apiKey": PUBLIC_API_KEY,
    "User-Agent": "ObraSignal Lithuania VPT snapshot connector/1.0",
}
ACTIONABLE_STATUS = "Bid submission"
EXCLUDED_PROCEDURES = {"Preliminary Market Consultation"}
TERMINAL_STATUS_MAP = {
    "Awarded": "awarded",
    "Cancelled": "cancelled",
}


def _text(value):
    return str(value or "").strip()


def _source_date(value, *, critical=False):
    """Parse CVP IS local timestamps and reject obviously corrupt calendar years."""
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.strptime(text, "%d-%m-%Y %H:%M:%S")
    except ValueError:
        return None
    # Live data contains at least one legacy publication date with year 0028.
    # Such values must not become ordering/cursor facts. Deadline callers can
    # decide separately whether a missing parse is critical to actionability.
    if parsed.year < 2000 or parsed.year > 2100:
        return None
    parsed = parsed.replace(tzinfo=VILNIUS).astimezone(timezone.utc)
    return parsed


def _cursor_date(value):
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc(value):
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _cpv_codes(value):
    out = []
    for token in re.split(r"[,;|]", _text(value)):
        code = token.strip()
        if code and code not in out:
            out.append(code)
    return out


def _stable_id(row):
    if not isinstance(row, dict):
        return ""
    value = row.get("id")
    if isinstance(value, bool) or value in (None, ""):
        return ""
    text = str(value).strip()
    return text if text else ""


def _is_works(row):
    return _text(row.get("procurementType")).lower() == "works"


def _is_market_consultation(row):
    return _text(row.get("procedure")) in EXCLUDED_PROCEDURES


def _state_from_row(row):
    external_id = _stable_id(row)
    if not external_id:
        raise RuntimeError(f"{SOURCE} snapshot row missing stable id; cursor not advanced")

    cpvs = _cpv_codes(row.get("cpvCodes"))
    publication = _source_date(row.get("datePublished"))
    deadline = _source_date(row.get("tenderSubmissionDeadline"), critical=True)
    cft_unique = _text(row.get("cftCaUniqueId"))
    if cft_unique == "---":
        cft_unique = ""

    return {
        "external_id": external_id,
        "procedure_id": external_id,
        "title": _text(row.get("title")),
        "description": _text(row.get("description")),
        "buyer": _text(row.get("caName")),
        "buyer_national_id": _text(row.get("caNumber")),
        "procurement_type": _text(row.get("procurementType")),
        "procedure": _text(row.get("procedure")),
        "source_status": _text(row.get("status")),
        "active_cycle": row.get("activeCycle"),
        "cft_ca_unique_id": cft_unique,
        "cft_involves": _text(row.get("cftInvolves")),
        "cpv_codes": cpvs,
        "nuts_code": _text(row.get("nutsCode")),
        "deadline": _utc(deadline),
        "published_at": _utc(publication),
        "estimated_value": row.get("estimatedValue"),
        "evaluation_mechanism": _text(row.get("evaluationMechanism")),
        "directive": _text(row.get("directive")),
        "eu_funding": row.get("euFunding"),
        "contract_duration": _text(row.get("contractDuration")),
        "tender_validity": _text(row.get("tenderValidity")),
        "contract_awarded_in_lots": row.get("contractAwardedInLots"),
        "award_date": _text(row.get("awardDate")),
        "contract_award_date": _text(row.get("contractAwardDate")),
        "url": HUMAN_URL.format(resource_id=external_id),
        "was_visible": False,
    }


def _actionability(state, now):
    if _text(state.get("procurement_type")).lower() != "works":
        return False, "not_works"
    if _text(state.get("procedure")) in EXCLUDED_PROCEDURES:
        return False, "preliminary_market_consultation"

    status = _text(state.get("source_status"))
    if status != ACTIONABLE_STATUS:
        return False, TERMINAL_STATUS_MAP.get(status, "source_inactive")

    raw_deadline = _text(state.get("deadline"))
    if not raw_deadline:
        return False, "deadline_missing_or_invalid"
    deadline = _cursor_date(raw_deadline)
    if deadline is None:
        return False, "deadline_missing_or_invalid"
    if deadline <= now:
        return False, "deadline_elapsed"
    return True, "open"


def _lifecycle_status(state, reason):
    if reason in {"awarded", "cancelled", "deadline_elapsed", "deadline_missing_or_invalid"}:
        return reason
    if reason == "preliminary_market_consultation":
        return "inactive"
    source_status = _text(state.get("source_status"))
    if source_status:
        return "inactive"
    return "inactive"


def _observation(state, *, actionable, lifecycle_status, lifecycle_reason, lifecycle_only=False):
    cpvs = list(state.get("cpv_codes") or [])
    primary = cpvs[0] if cpvs else ""
    published_at = _text(state.get("published_at"))
    estimated = state.get("estimated_value")
    row = {
        "source": SOURCE,
        "external_id": _text(state.get("external_id")),
        "title": _text(state.get("title")),
        "description": _text(state.get("description")),
        "buyer": _text(state.get("buyer")),
        "country": COUNTRY,
        "cpv": primary,
        "taxonomy": "CPV" if primary else "",
        "category_code": primary,
        "cpv_codes": cpvs,
        "value": "" if estimated in (None, "") else str(estimated),
        "currency": "EUR" if estimated not in (None, "") else "",
        "deadline": _text(state.get("deadline")),
        "publication_date": published_at[:10] if published_at else "",
        "published_at": published_at or None,
        "source_updated_at": None,
        "url": _text(state.get("url")) or PUBLIC_SITE,
        "market": "GLOBAL",
        "place": _text(state.get("nuts_code")),
        "source_status": _text(state.get("source_status")),
        "source_phase": "notice",
        "signal_type": "TENDER",
        "procurement_method": _text(state.get("procedure")),
        "contract_type": "works",
        "source_reference": _text(state.get("external_id")),
        "notice_identifier": _text(state.get("external_id")),
        "procedure_reference": _text(state.get("cft_ca_unique_id")) or _text(state.get("external_id")),
        "buyer_national_id": _text(state.get("buyer_national_id")),
        "cft_ca_unique_id": _text(state.get("cft_ca_unique_id")),
        "cft_involves": _text(state.get("cft_involves")),
        "active_cycle": state.get("active_cycle"),
        "evaluation_mechanism": _text(state.get("evaluation_mechanism")),
        "directive": _text(state.get("directive")),
        "eu_funding": state.get("eu_funding"),
        "contract_duration": _text(state.get("contract_duration")),
        "tender_validity": _text(state.get("tender_validity")),
        # Preserve the publisher flag but do not claim lot-level ingestion.
        "contract_awarded_in_lots": state.get("contract_awarded_in_lots"),
        "attribution": ATTRIBUTION,
        "source_catalog_url": PUBLIC_SITE,
        "source_api_url": ENDPOINT,
        "is_actionable": bool(actionable),
        "lifecycle_status": lifecycle_status,
        "lifecycle_reason": lifecycle_reason,
    }
    if lifecycle_only:
        row["_lifecycle_only"] = True
    return row


@dataclass
class LithuaniaVPTCursor:
    observed_through: str
    tracked: dict

    @classmethod
    def empty(cls):
        return cls(observed_through="", tracked={})

    @classmethod
    def decode(cls, value):
        if value in (None, ""):
            return cls.empty()
        try:
            payload = json.loads(value)
        except Exception as exc:
            raise RuntimeError(f"invalid {SOURCE} cursor; cursor not advanced") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"invalid {SOURCE} cursor; cursor not advanced")
        try:
            version = int(payload.get("version") or 1)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"invalid {SOURCE} cursor version; cursor not advanced") from exc
        if version != 1:
            raise RuntimeError(f"invalid {SOURCE} cursor version; cursor not advanced")
        tracked = payload.get("tracked") or {}
        if not isinstance(tracked, dict):
            raise RuntimeError(f"invalid {SOURCE} cursor tracked state; cursor not advanced")
        return cls(
            observed_through=_text(payload.get("observed_through")),
            tracked=deepcopy(tracked),
        )

    def encode(self):
        return json.dumps(
            {
                "version": 1,
                "observed_through": self.observed_through,
                "tracked": self.tracked,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


class LithuaniaVPTSnapshotConnector:
    def __init__(self, *, session=None, page_size=2000, max_pages=100):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)
        self.page_size = int(page_size)
        self.max_pages = int(max_pages)
        if self.page_size < 1 or self.page_size > 2000:
            raise ValueError("page_size must be between 1 and the live-validated maximum 2000")
        if self.max_pages < 1:
            raise ValueError("max_pages must be >= 1")

    def _page(self, page_num):
        response = self.session.post(
            ENDPOINT,
            headers=HEADERS,
            json={"pageSize": self.page_size, "pageNum": int(page_num)},
            timeout=60,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError(f"{SOURCE} page {page_num} returned invalid JSON; cursor not advanced") from exc
        if not isinstance(payload, list):
            raise RuntimeError(f"{SOURCE} page {page_num} returned non-list JSON; cursor not advanced")
        if len(payload) > self.page_size:
            raise RuntimeError(f"{SOURCE} page {page_num} exceeds requested page_size; cursor not advanced")
        if any(not isinstance(row, dict) for row in payload):
            raise RuntimeError(f"{SOURCE} page {page_num} contains malformed row; cursor not advanced")
        return payload

    def _snapshot(self):
        rows_by_id = {}
        saw_terminator = False
        for page_num in range(1, self.max_pages + 1):
            rows = self._page(page_num)
            if page_num == 1 and not rows:
                raise RuntimeError(f"{SOURCE} unexpected empty first snapshot page; cursor not advanced")
            for row in rows:
                external_id = _stable_id(row)
                if not external_id:
                    raise RuntimeError(f"{SOURCE} snapshot row missing stable id; cursor not advanced")
                if external_id in rows_by_id:
                    raise RuntimeError(f"{SOURCE} duplicate snapshot id {external_id}; cursor not advanced")
                rows_by_id[external_id] = row
            if len(rows) < self.page_size:
                saw_terminator = True
                break
        if not saw_terminator:
            raise RuntimeError(f"{SOURCE} snapshot exceeds max_pages={self.max_pages}; cursor not advanced")
        return rows_by_id

    def fetch_incremental(self, *, watermark=None, now=None):
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        now = now.astimezone(timezone.utc)

        cursor = LithuaniaVPTCursor.decode(watermark)
        observed = _cursor_date(cursor.observed_through)
        if cursor.observed_through and observed is None:
            raise RuntimeError(f"invalid {SOURCE} cursor observed_through; cursor not advanced")
        if observed is not None and observed > now + timedelta(minutes=5):
            raise RuntimeError(f"{SOURCE} cursor is in the future; cursor not advanced")

        snapshot = self._snapshot()
        current_works = {}
        for external_id, raw in snapshot.items():
            if not _is_works(raw):
                continue
            state = _state_from_row(raw)
            current_works[external_id] = state

        observations = []
        next_tracked = {}
        all_ids = set(cursor.tracked) | set(current_works)
        for external_id in sorted(all_ids, key=lambda value: (len(value), value)):
            previous = cursor.tracked.get(external_id)
            current = current_works.get(external_id)

            if current is None:
                if isinstance(previous, dict) and previous.get("was_visible"):
                    observations.append(
                        _observation(
                            previous,
                            actionable=False,
                            lifecycle_status="inactive",
                            lifecycle_reason="missing_from_complete_snapshot",
                            lifecycle_only=True,
                        )
                    )
                continue

            actionable, reason = _actionability(current, now)
            if actionable:
                current["was_visible"] = True
                next_tracked[external_id] = current
                if previous != current:
                    observations.append(
                        _observation(
                            current,
                            actionable=True,
                            lifecycle_status="open",
                            lifecycle_reason="works_bid_submission_with_future_deadline",
                        )
                    )
                continue

            if isinstance(previous, dict) and previous.get("was_visible"):
                current["was_visible"] = True
                observations.append(
                    _observation(
                        current,
                        actionable=False,
                        lifecycle_status=_lifecycle_status(current, reason),
                        lifecycle_reason=reason,
                        lifecycle_only=True,
                    )
                )
            # Non-actionable rows are deliberately not tracked after reconciliation.
            # A future full snapshot can rediscover the id if it becomes actionable.

        next_cursor = LithuaniaVPTCursor(
            observed_through=_utc(now),
            tracked=next_tracked,
        )
        return observations, next_cursor.encode()


def fetch_lithuania_vpt_tenders(*, watermark=None, session=None, now=None):
    connector = LithuaniaVPTSnapshotConnector(session=session)
    return connector.fetch_incremental(watermark=watermark, now=now)
