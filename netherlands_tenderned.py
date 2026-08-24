"""Netherlands TenderNed public list/detail construction connector.

TenderNed exposes a no-login JSON publication list and per-publication JSON
resource beneath ``/papi/tenderned-rs-tns/v2/publicaties``. Live validation on
2026-08-24 proved Spring-style page/size pagination (100 accepted, 250 rejected),
publication-date descending ordering, publisher-native Works semantics, CPV/NUTS,
structured deadlines, rectifications and terminal award/early-end publications.

Important invariants:
- ``kenmerk`` is the stable commercial procedure identity; ``publicatieId`` is
  the publication/event identity.
- ordering is by publication *date*, not monotonically by ``publicatieId``.
- every scanned page must report the same ``totalElements`` and publication ids
  may not repeat across pages; otherwise the cursor is not advanced.
- only publisher-native ``typeOpdrachtCode.code == 'W'`` can create/update a
  construction opportunity.
- lifecycle-only observations are emitted for previously visible procedures but
  never become legacy tender rows in the runtime plugin.
- raw PDFs, HTML and contact/person payloads are not persisted.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
from zoneinfo import ZoneInfo

import requests


SOURCE = "NL_TENDERNED"
COUNTRY = "NLD"
BASE = "https://www.tenderned.nl/papi/tenderned-rs-tns/v2/publicaties"
HUMAN_URL = "https://www.tenderned.nl/aankondigingen/overzicht/{publication_id}"
CATALOG_URL = "https://www.tenderned.nl/cms/nl/aanbesteden-in-cijfers/datasets-aanbestedingen"
ATTRIBUTION = "TenderNed — Nederlandse aanbestedingen"
AMSTERDAM = ZoneInfo("Europe/Amsterdam")
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal TenderNed connector/1.0 (+official public-data ingestion)",
}
OPEN_CODES = {"AAO", "REC"}
MARKET_CONSULTATION_CODES = {"MAC"}
TERMINAL_AWARD_CODES = {"AGO"}
TERMINAL_EARLY_CODES = {"VBE"}


def _text(value):
    return "" if value is None else str(value).strip()


def _code(value):
    if isinstance(value, dict):
        return _text(value.get("code"))
    return _text(value)


def _description(value):
    if isinstance(value, dict):
        return _text(value.get("omschrijving"))
    return ""


def _local_dt(value):
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=AMSTERDAM)
    return parsed.astimezone(timezone.utc)


def _utc(value):
    parsed = _local_dt(value)
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z") if parsed else ""


def _source_date(value):
    text = _text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _publication_id(row):
    value = row.get("publicatieId") if isinstance(row, dict) else None
    if isinstance(value, bool) or value in (None, ""):
        return ""
    text = str(value).strip()
    return text if text.isdigit() else ""


def _kenmerk(row):
    value = row.get("kenmerk") if isinstance(row, dict) else None
    if isinstance(value, bool) or value in (None, ""):
        return ""
    text = str(value).strip()
    return text if text else ""


def _is_works_summary(row):
    return _code(row.get("typeOpdracht")) == "W"


def _is_works_detail(row):
    return _code(row.get("typeOpdrachtCode")) == "W"


def _cpvs(row):
    out = []
    for item in row.get("cpvCodes") or []:
        if not isinstance(item, dict):
            continue
        code = _text(item.get("code"))
        if not code or any(existing["id"] == code for existing in out):
            continue
        out.append({
            "id": code,
            "description": _text(item.get("omschrijving")),
            "primary": bool(item.get("isHoofdOpdracht")),
        })
    out.sort(key=lambda item: (not item["primary"], item["id"]))
    return out


def _nuts(row):
    out = []
    for item in row.get("nutsCodes") or []:
        if not isinstance(item, dict):
            continue
        code = _text(item.get("code"))
        if code and code not in [entry["id"] for entry in out]:
            out.append({"id": code, "description": _text(item.get("omschrijving"))})
    return out


def _state_from_detail(row, *, was_actionable=False):
    if not isinstance(row, dict) or not _is_works_detail(row):
        return None
    publicatie_id = _publication_id(row)
    kenmerk = _kenmerk(row)
    published = _utc(row.get("publicatieDatum"))
    if not publicatie_id or not kenmerk or not published:
        raise RuntimeError(f"{SOURCE} Works detail missing publicatieId/kenmerk/publicatieDatum; cursor not advanced")
    cpvs = _cpvs(row)
    nuts = _nuts(row)
    return {
        "kenmerk": kenmerk,
        "publication_id": publicatie_id,
        "title": _text(row.get("aanbestedingNaam")),
        "description": _text(row.get("opdrachtBeschrijving")),
        "buyer": _text(row.get("opdrachtgeverNaam")),
        "published_at": published,
        "source_updated_at": published,
        "deadline": _utc(row.get("sluitingsDatum")),
        "publication_code": _text(row.get("publicatieCode")),
        "publication_type": _text(row.get("typePublicatie")),
        "announcement_code": _code(row.get("aankondigingCode")),
        "announcement_description": _description(row.get("aankondigingCode")),
        "procedure_code": _code(row.get("procedureCode")),
        "procedure_description": _description(row.get("procedureCode")),
        "status": _text(row.get("aanbestedingStatus")),
        "cpv_classifications": cpvs,
        "nuts_classifications": nuts,
        "is_awarded": bool(row.get("isGegund")),
        "is_completed": bool(row.get("afgerondeAanbesteding")),
        "is_early_ended": bool(row.get("isVroegtijdigBeeindigd")),
        "national_or_eu": _code(row.get("nationaalOfEuropeesCode")),
        "legal_framework": _description(row.get("juridischKaderCode")),
        "digital_submission": bool(row.get("isDigitaalInschrijvenMogelijk")),
        "reference_number": _text(row.get("referentieNummer")),
        "was_actionable": bool(was_actionable),
    }


def _terminal(state):
    code = _text(state.get("announcement_code"))
    if state.get("is_early_ended") or code in TERMINAL_EARLY_CODES:
        return "terminated", "TenderNed reports early termination"
    if state.get("is_awarded") or state.get("is_completed") or code in TERMINAL_AWARD_CODES:
        return "awarded", "TenderNed reports award/completed procurement"
    if _text(state.get("status")) == "EIN":
        return "inactive", "TenderNed procurement status is EIN"
    return None


def _is_open_state(state, now):
    if _text(state.get("announcement_code")) in MARKET_CONSULTATION_CODES:
        return False, "market_consultation"
    terminal = _terminal(state)
    if terminal:
        return False, terminal[0]
    if _text(state.get("status")) != "AAN":
        return False, "source_inactive"
    if _text(state.get("announcement_code")) not in OPEN_CODES:
        return False, "not_open_tender_publication"
    deadline = _local_dt(state.get("deadline"))
    if deadline is None:
        return False, "deadline_missing"
    if deadline <= now:
        return False, "deadline_elapsed"
    return True, "open"


def _observation(state, *, actionable, lifecycle_status, lifecycle_reason, lifecycle_only=False):
    cpvs = [entry for entry in state.get("cpv_classifications") or [] if isinstance(entry, dict) and _text(entry.get("id"))]
    primary = _text(cpvs[0].get("id")) if cpvs else ""
    nuts = [entry for entry in state.get("nuts_classifications") or [] if isinstance(entry, dict) and _text(entry.get("id"))]
    publication_id = _text(state.get("publication_id"))
    row = {
        "source": SOURCE,
        "external_id": _text(state.get("kenmerk")),
        "title": _text(state.get("title")),
        "description": _text(state.get("description")),
        "buyer": _text(state.get("buyer")),
        "country": COUNTRY,
        "cpv": primary,
        "taxonomy": "CPV" if primary else "",
        "category_code": primary,
        "cpv_codes": [_text(entry.get("id")) for entry in cpvs],
        "cpv_classifications": cpvs,
        "value": "",
        "currency": "",
        "deadline": _text(state.get("deadline")),
        "publication_date": _text(state.get("published_at"))[:10],
        "published_at": _text(state.get("published_at")) or None,
        "source_updated_at": _text(state.get("source_updated_at")) or None,
        "url": HUMAN_URL.format(publication_id=publication_id) if publication_id else CATALOG_URL,
        "market": "GLOBAL",
        "place": " | ".join(_text(entry.get("description")) or _text(entry.get("id")) for entry in nuts),
        "nuts_codes": [_text(entry.get("id")) for entry in nuts],
        "source_status": _text(state.get("status")),
        "source_phase": _text(state.get("announcement_description")) or _text(state.get("announcement_code")),
        "signal_type": "TENDER",
        "procurement_method": _text(state.get("procedure_description")) or _text(state.get("procedure_code")),
        "contract_type": "works",
        "source_reference": publication_id,
        "notice_identifier": publication_id,
        "procedure_reference": _text(state.get("kenmerk")),
        "publication_code": _text(state.get("publication_code")),
        "publication_type": _text(state.get("publication_type")),
        "announcement_code": _text(state.get("announcement_code")),
        "reference_number": _text(state.get("reference_number")),
        "national_or_eu": _text(state.get("national_or_eu")),
        "legal_framework": _text(state.get("legal_framework")),
        "digital_submission": bool(state.get("digital_submission")),
        "attribution": ATTRIBUTION,
        "source_catalog_url": CATALOG_URL,
        "source_api_url": BASE,
        "source_modified": True,
        "is_actionable": bool(actionable),
        "lifecycle_status": lifecycle_status,
        "lifecycle_reason": lifecycle_reason,
    }
    if lifecycle_only or not actionable:
        row["_lifecycle_only"] = True
    return row


@dataclass
class TenderNedCursor:
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
            payload = json.loads(str(value))
        except Exception as exc:
            raise RuntimeError(f"invalid {SOURCE} cursor JSON; cursor not advanced") from exc
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
        observed = _text(payload.get("observed_through"))
        if observed and _local_dt(observed) is None:
            raise RuntimeError(f"invalid {SOURCE} cursor observed_through; cursor not advanced")
        return cls(observed_through=observed, tracked=deepcopy(tracked))

    def encode(self):
        return json.dumps(
            {"version": 1, "observed_through": self.observed_through, "tracked": self.tracked},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


class TenderNedPublicConnector:
    def __init__(
        self,
        *,
        session=None,
        page_size=100,
        initial_lookback_days=45,
        overlap_days=2,
        max_pages=90,
        max_detail_requests=2500,
        timeout=60,
    ):
        self.session = session or requests.Session()
        self.page_size = int(page_size)
        self.initial_lookback_days = max(1, int(initial_lookback_days))
        self.overlap_days = max(1, int(overlap_days))
        self.max_pages = max(1, int(max_pages))
        self.max_detail_requests = max(1, int(max_detail_requests))
        self.timeout = int(timeout)
        if self.page_size < 1 or self.page_size > 100:
            raise ValueError("page_size must be between 1 and live-validated maximum 100")
        self._detail_requests = 0

    def _page(self, page):
        response = self.session.get(
            BASE,
            params={"page": int(page), "size": self.page_size},
            headers=HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError(f"{SOURCE} list returned invalid JSON; cursor not advanced") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("content"), list):
            raise RuntimeError(f"{SOURCE} list returned malformed page; cursor not advanced")
        rows = payload["content"]
        if any(not isinstance(row, dict) for row in rows):
            raise RuntimeError(f"{SOURCE} list page contains malformed row; cursor not advanced")
        try:
            total = int(payload.get("totalElements"))
            number = int(payload.get("number"))
            size = int(payload.get("size"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{SOURCE} list page missing pagination metadata; cursor not advanced") from exc
        if number != int(page) or size != self.page_size:
            raise RuntimeError(f"{SOURCE} pagination metadata mismatch; cursor not advanced")
        return rows, total

    def _detail(self, publication_id):
        self._detail_requests += 1
        if self._detail_requests > self.max_detail_requests:
            raise RuntimeError(f"{SOURCE} exceeded max_detail_requests={self.max_detail_requests}; cursor not advanced")
        response = self.session.get(
            f"{BASE}/{publication_id}",
            headers=HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError(f"{SOURCE} detail {publication_id} returned invalid JSON; cursor not advanced") from exc
        if not isinstance(payload, dict) or _publication_id(payload) != str(publication_id):
            raise RuntimeError(f"{SOURCE} detail identity mismatch for {publication_id}; cursor not advanced")
        return payload

    def _discover(self, start_date):
        discovered = []
        seen = set()
        expected_total = None
        reached_cutoff = False
        previous_oldest = None
        for page in range(self.max_pages):
            rows, total = self._page(page)
            if expected_total is None:
                expected_total = total
            elif total != expected_total:
                raise RuntimeError(f"{SOURCE} totalElements changed during scan; cursor not advanced")
            if not rows:
                reached_cutoff = True
                break
            dates = [_source_date(row.get("publicatieDatum")) for row in rows]
            if any(item is None for item in dates):
                raise RuntimeError(f"{SOURCE} list row missing valid publicatieDatum; cursor not advanced")
            if any(a < b for a, b in zip(dates, dates[1:])):
                raise RuntimeError(f"{SOURCE} list is not publication-date descending; cursor not advanced")
            if previous_oldest is not None and dates[0] > previous_oldest:
                raise RuntimeError(f"{SOURCE} page ordering regressed; cursor not advanced")
            previous_oldest = dates[-1]
            for row, published_date in zip(rows, dates):
                publicatie_id = _publication_id(row)
                if not publicatie_id:
                    raise RuntimeError(f"{SOURCE} list row missing publicatieId; cursor not advanced")
                if publicatie_id in seen:
                    raise RuntimeError(f"{SOURCE} duplicate publicatieId across pages; cursor not advanced")
                seen.add(publicatie_id)
                if published_date >= start_date:
                    discovered.append(row)
            if dates[-1] < start_date:
                reached_cutoff = True
                break
        if not reached_cutoff:
            raise RuntimeError(f"{SOURCE} discovery exceeds max_pages={self.max_pages}; cursor not advanced")
        return discovered

    @staticmethod
    def _event_key(row):
        published = _local_dt(row.get("publicatieDatum")) if isinstance(row, dict) else None
        try:
            publication_id = int(_publication_id(row) or 0)
        except ValueError:
            publication_id = 0
        return (published or datetime.min.replace(tzinfo=timezone.utc), publication_id)

    def _apply_events(self, details, tracked):
        for row in sorted(details, key=self._event_key):
            if not _is_works_detail(row):
                continue
            kenmerk = _kenmerk(row)
            if not kenmerk:
                raise RuntimeError(f"{SOURCE} Works detail missing kenmerk; cursor not advanced")
            previous = tracked.get(kenmerk)
            state = _state_from_detail(row, was_actionable=bool(previous and previous.get("was_actionable")))
            terminal = _terminal(state)
            if terminal:
                if previous:
                    state["was_actionable"] = bool(previous.get("was_actionable"))
                    state["closed_status"], state["closed_reason"] = terminal
                    tracked[kenmerk] = state
                continue
            # Only open/rectification publications may establish tracked Works
            # provenance. Other non-terminal publication types are ignored unless
            # the procedure was already tracked.
            if _text(state.get("announcement_code")) in OPEN_CODES or previous:
                tracked[kenmerk] = state

    def _finalize(self, tracked, now):
        observations = []
        survivors = {}
        for kenmerk, state in tracked.items():
            terminal = _terminal(state)
            if terminal:
                if state.get("was_actionable"):
                    observations.append(_observation(
                        state,
                        actionable=False,
                        lifecycle_status=_text(state.get("closed_status")) or terminal[0],
                        lifecycle_reason=_text(state.get("closed_reason")) or terminal[1],
                        lifecycle_only=True,
                    ))
                continue
            actionable, reason = _is_open_state(state, now)
            if actionable:
                state["was_actionable"] = True
                survivors[kenmerk] = state
                observations.append(_observation(
                    state,
                    actionable=True,
                    lifecycle_status="active",
                    lifecycle_reason="TenderNed reports Works procurement with future submission deadline",
                ))
                continue
            if reason == "deadline_missing":
                if state.get("was_actionable"):
                    observations.append(_observation(
                        state,
                        actionable=False,
                        lifecycle_status="deadline_missing",
                        lifecycle_reason="TenderNed Works publication no longer has a valid submission deadline",
                        lifecycle_only=True,
                    ))
                    state["was_actionable"] = False
                survivors[kenmerk] = state
                continue
            if state.get("was_actionable"):
                status = "deadline_elapsed" if reason == "deadline_elapsed" else "inactive"
                observations.append(_observation(
                    state,
                    actionable=False,
                    lifecycle_status=status,
                    lifecycle_reason=reason,
                    lifecycle_only=True,
                ))
        return observations, survivors

    def fetch_incremental(self, *, watermark=None, now=None):
        self._detail_requests = 0
        current = _local_dt(now) or datetime.now(timezone.utc)
        cursor = TenderNedCursor.decode(watermark)
        observed = _local_dt(cursor.observed_through) if cursor.observed_through else None
        if observed and observed > current + timedelta(minutes=5):
            raise RuntimeError(f"{SOURCE} cursor is in the future; cursor not advanced")
        tracked = deepcopy(cursor.tracked)
        if observed:
            start_date = (observed.astimezone(AMSTERDAM) - timedelta(days=self.overlap_days)).date()
        else:
            start_date = (current.astimezone(AMSTERDAM) - timedelta(days=self.initial_lookback_days)).date()

        summaries = self._discover(start_date)
        details = []
        for summary in summaries:
            if not _is_works_summary(summary):
                continue
            publicatie_id = _publication_id(summary)
            details.append(self._detail(publicatie_id))
        self._apply_events(details, tracked)
        observations, tracked = self._finalize(tracked, current)
        next_cursor = TenderNedCursor(
            observed_through=current.isoformat(timespec="seconds").replace("+00:00", "Z"),
            tracked=tracked,
        ).encode()
        return observations, next_cursor


def build_tenderned_connector(*, session=None, **kwargs):
    return TenderNedPublicConnector(session=session, **kwargs)


def fetch_tenderned_tenders(*, watermark=None, now=None, connector=None):
    client = connector or build_tenderned_connector()
    return client.fetch_incremental(watermark=watermark, now=now)
