"""Italy ANAC BDNCP / Pubblicita a Valore Legale Works tender connector.

The public PVL JSON API exposes legal-publicity notices without authentication at
``/api/v0/avvisi``. Production reads bounded publication-day windows and rebuilds
current lot state from publisher records. Commercial identity is the publisher CIG
for each lot. Only lots whose native ``natura_principale`` is ``Lavori`` can become
ObraSignal opportunities; title/CPV keyword inference is never used.

PVL rectifications carry the lot payload again. A later ``rettifica`` therefore
updates the same CIG instead of creating a duplicate. PVL currently exposes CPV as a
human label in this payload, not a verified numeric CPV code, so the label is kept as
source metadata and is never masqueraded as a CPV code.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests


SOURCE = "IT_ANAC"
COUNTRY = "ITA"
ANAC_PVL_BASE = "https://pubblicitalegale.anticorruzione.it"
ANAC_PVL_API_BASE = f"{ANAC_PVL_BASE}/api/v0"
ANAC_PVL_AVVISI = f"{ANAC_PVL_API_BASE}/avvisi"
ANAC_PVL_HUMAN = f"{ANAC_PVL_BASE}/bandi/{{notice_id}}"
ANAC_ATTRIBUTION = "ANAC — BDNCP, Pubblicita a Valore Legale"
ANAC_DATASET = "BDNCP — Pubblicita a Valore Legale (PVL)"
ANAC_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal ANAC PVL connector/1.0 (+official public-data ingestion)",
}
ROME = ZoneInfo("Europe/Rome")
_SUPPORTED_TYPES = frozenset(("avviso", "rettifica"))


def _text(value):
    return "" if value is None else " ".join(str(value).split())


def _dt(value):
    if isinstance(value, datetime):
        parsed = value
    elif value:
        text = str(value).strip()
        # PVL sometimes emits a date plus UTC offset (YYYY-MM-DD+02:00) in a
        # lot-level fallback field. That string has no publisher-supplied clock
        # time and must not be silently interpreted as one.
        if "T" not in text and " " not in text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ROME)
    return parsed.astimezone(timezone.utc)


def _utc(value):
    parsed = _dt(value)
    return None if parsed is None else parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _day(value, *, label="day"):
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError as exc:
        raise RuntimeError(f"invalid {SOURCE} cursor {label}") from exc


def _human_url(notice_id):
    value = _text(notice_id)
    return ANAC_PVL_HUMAN.format(notice_id=quote(value, safe="")) if value else ""


def _template(payload):
    candidates = payload.get("templates")
    if not isinstance(candidates, list):
        candidates = payload.get("template")
    if not isinstance(candidates, list):
        return {}
    wrappers = [item for item in candidates if isinstance(item, dict)]
    if not wrappers:
        return {}
    preferred = next((item for item in wrappers if _text(item.get("lingua")).lower() == "it"), wrappers[0])
    inner = preferred.get("template")
    return inner if isinstance(inner, dict) else {}


def _sections(payload):
    value = _template(payload).get("sections")
    return [section for section in value if isinstance(section, dict)] if isinstance(value, list) else []


def _section(payload, prefix):
    prefix = str(prefix)
    for section in _sections(payload):
        if _text(section.get("name")).startswith(prefix):
            return section
    return {}


def _metadata(payload):
    value = _template(payload).get("metadata")
    return value if isinstance(value, dict) else {}


def _lots(payload):
    value = _section(payload, "SEZ. C").get("items")
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _buyer(payload):
    fields = _section(payload, "SEZ. A").get("fields")
    fields = fields if isinstance(fields, dict) else {}
    subjects = fields.get("soggetti_sa")
    if not isinstance(subjects, list):
        return ""
    names = []
    for subject in subjects:
        if not isinstance(subject, dict):
            continue
        name = _text(subject.get("denominazione_amministrazione"))
        if name and name not in names:
            names.append(name)
    return " | ".join(names)


def _general_fields(payload):
    value = _section(payload, "SEZ. B").get("fields")
    return value if isinstance(value, dict) else {}


def _place(lot):
    values = []
    for key in ("luogo_istat", "luogo_nuts"):
        value = _text(lot.get(key))
        if value and value not in values:
            values.append(value)
    return " | ".join(values)


def _categories(lot):
    value = lot.get("categorie")
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if not isinstance(item, dict):
            continue
        code = _text(item.get("codice"))
        description = _text(item.get("descrizione"))
        if not code and not description:
            continue
        entry = {"code": code, "description": description}
        if entry not in out:
            out.append(entry)
    return out


def _effective_deadline(payload, lot):
    # Prefer a lot-level timestamp only when it actually contains a clock time;
    # otherwise use PVL's precise top-level dataScadenza.
    for value in (lot.get("termine_ricezione"), lot.get("termine_invito")):
        parsed = _utc(value)
        if parsed:
            return parsed
    return _utc(payload.get("dataScadenza")) or ""


def _event_key(state):
    published = _dt(state.get("source_updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
    created = _dt(state.get("data_created_at")) or datetime.min.replace(tzinfo=timezone.utc)
    return (published, created, _text(state.get("notice_id")))


def _notice_events(payload, *, publication_day):
    if not isinstance(payload, dict):
        return []
    if _text(payload.get("tipologia")).upper() not in ("", "BANDI"):
        return []

    notice_id = _text(payload.get("idAvviso"))
    procedure_id = _text(payload.get("idAppalto"))
    notice_type = _text(payload.get("tipo")).lower()
    source_updated_at = _utc(payload.get("dataPubblicazione"))
    created_at = _utc(payload.get("dataCreazione"))
    lots = _lots(payload)
    if not lots:
        return []

    works = [lot for lot in lots if _text(lot.get("natura_principale")).casefold() == "lavori"]
    if works and notice_type not in _SUPPORTED_TYPES:
        raise RuntimeError(f"{SOURCE} Works notice has unsupported tipo={notice_type!r}; cursor not advanced")
    if works and (not notice_id or not procedure_id or not source_updated_at):
        raise RuntimeError(f"{SOURCE} Works notice missing idAvviso/idAppalto/dataPubblicazione; cursor not advanced")

    metadata = _metadata(payload)
    general = _general_fields(payload)
    project_title = _text(metadata.get("titolo")) or _text(metadata.get("descrizione"))
    project_description = _text(metadata.get("descrizione")) or project_title
    buyer = _buyer(payload)
    total_lots = len(lots)
    events = []

    for lot in lots:
        cig = _text(lot.get("cig"))
        nature = _text(lot.get("natura_principale"))
        is_works = nature.casefold() == "lavori"
        if is_works and not cig:
            raise RuntimeError(f"{SOURCE} Works lot missing CIG; cursor not advanced")
        if not cig:
            continue
        if not is_works and not source_updated_at:
            continue

        lot_description = _text(lot.get("descrizione"))
        if total_lots > 1 and lot_description:
            title = f"{project_title} — {lot_description}" if project_title and lot_description != project_title else lot_description
        else:
            title = project_title or lot_description or cig
        categories = _categories(lot)
        value = lot.get("valore_complessivo_stimato")
        if not isinstance(value, (int, float, str)):
            value = ""
        events.append({
            "external_id": cig,
            "cig": cig,
            "procedure_id": procedure_id,
            "notice_id": notice_id,
            "publication_day": publication_day,
            "source_updated_at": source_updated_at,
            "data_created_at": created_at,
            "first_published_at": source_updated_at,
            "notice_type": notice_type,
            "tipologia": _text(payload.get("tipologia")),
            "codice_scheda": _text(payload.get("codiceScheda")),
            "codice_eform": _text(payload.get("codiceEform")),
            "active": bool(payload.get("attivo")),
            "obscured": bool(payload.get("oscurato")),
            "is_works": is_works,
            "nature": nature,
            "title": title,
            "description": project_description or lot_description or title,
            "lot_description": lot_description,
            "buyer": buyer,
            "place": _place(lot),
            "deadline": _effective_deadline(payload, lot),
            "value": str(value) if value != "" else "",
            "currency": "EUR" if value != "" else "",
            "cpv_label": _text(lot.get("cpv")),
            "work_categories": categories,
            "procurement_method": _text(general.get("tipo_procedura_aggiudicazione")),
            "documents_url": _text(lot.get("documenti_di_gara_link")) or _text(general.get("documenti_di_gara_link")),
            "ted_url": _text(metadata.get("link_eform_ted")),
            "was_visible": False,
        })
    return events


def _merge_state(current, incoming):
    if current is None:
        return deepcopy(incoming)
    if _event_key(incoming) <= _event_key(current):
        return current
    updated = deepcopy(incoming)
    updated["was_visible"] = bool(current.get("was_visible")) or bool(incoming.get("was_visible"))
    first_values = [
        _text(value)
        for value in (current.get("first_published_at"), incoming.get("first_published_at"))
        if _text(value)
    ]
    if first_values:
        updated["first_published_at"] = min(first_values)
    return updated


def _observation(state, *, actionable, lifecycle_status, lifecycle_reason, lifecycle_only=False):
    categories = [item for item in state.get("work_categories", []) if isinstance(item, dict)]
    category_codes = [_text(item.get("code")) for item in categories if _text(item.get("code"))]
    row = {
        "source": SOURCE,
        "external_id": _text(state.get("external_id")),
        "title": _text(state.get("title")),
        "description": _text(state.get("description")),
        "buyer": _text(state.get("buyer")),
        "country": COUNTRY,
        # PVL currently exposes a CPV label here, not a verified numeric code.
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
        "url": _human_url(state.get("notice_id")),
        "market": "GLOBAL",
        "place": _text(state.get("place")),
        "source_status": _text(state.get("notice_type")),
        "source_phase": _text(state.get("tipologia")) or "BANDI",
        "signal_type": "TENDER",
        "procurement_method": _text(state.get("procurement_method")),
        "contract_type": "works",
        "source_reference": _text(state.get("notice_id")),
        "notice_identifier": _text(state.get("notice_id")),
        "anac_cig": _text(state.get("cig")),
        "anac_appalto_id": _text(state.get("procedure_id")),
        "anac_cpv_label": _text(state.get("cpv_label")),
        "anac_work_category_codes": category_codes,
        "anac_work_categories": categories,
        "anac_codice_scheda": _text(state.get("codice_scheda")),
        "anac_codice_eform": _text(state.get("codice_eform")),
        "anac_documents_url": _text(state.get("documents_url")),
        "anac_ted_url": _text(state.get("ted_url")),
        "attribution": ANAC_ATTRIBUTION,
        "source_dataset": ANAC_DATASET,
        "source_api_url": ANAC_PVL_AVVISI,
        "reuse_information": ANAC_PVL_BASE,
        "source_modified": True,
        "is_actionable": bool(actionable),
        "lifecycle_status": lifecycle_status,
        "lifecycle_reason": lifecycle_reason,
    }
    if lifecycle_only or not actionable:
        row["_lifecycle_only"] = True
    return row


@dataclass
class ANACPVLCursor:
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


class ANACPVLConnector:
    def __init__(
        self,
        *,
        session=None,
        initial_lookback_days=3,
        overlap_days=1,
        max_days_per_sync=4,
        page_size=100,
        max_pages_per_day=80,
        max_items_per_day=8000,
        timeout=60,
    ):
        self.session = session or requests.Session()
        self.initial_lookback_days = max(1, int(initial_lookback_days))
        self.max_days_per_sync = max(1, int(max_days_per_sync))
        self.overlap_days = min(max(0, int(overlap_days)), max(0, self.max_days_per_sync - 1))
        self.page_size = max(1, min(100, int(page_size)))
        self.max_pages_per_day = max(1, int(max_pages_per_day))
        self.max_items_per_day = max(self.page_size, int(max_items_per_day))
        self.timeout = max(1, int(timeout))

    @staticmethod
    def _target_day(now):
        current = _dt(now) or datetime.now(timezone.utc)
        return current.astimezone(ROME).date()

    def _get_page(self, day, page):
        response = self.session.get(
            ANAC_PVL_AVVISI,
            params={
                "dataPubblicazioneStart": day.strftime("%d/%m/%Y"),
                "dataPubblicazioneEnd": day.strftime("%d/%m/%Y"),
                "page": int(page),
                "size": self.page_size,
                "sortField": "dataPubblicazione",
                "sortDirection": "ASC",
                "ricercaArchivio": "true",
            },
            headers=ANAC_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{SOURCE} PVL response is not valid JSON; cursor not advanced") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("content"), list):
            raise RuntimeError(f"{SOURCE} PVL response has unsupported schema; cursor not advanced")
        try:
            number = int(payload.get("number"))
            total_pages = int(payload.get("totalPages"))
            total_elements = int(payload.get("totalElements"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{SOURCE} PVL pagination metadata is invalid; cursor not advanced") from exc
        if number != int(page) or total_pages < 0 or total_elements < 0:
            raise RuntimeError(f"{SOURCE} PVL pagination metadata is inconsistent; cursor not advanced")
        if total_pages > self.max_pages_per_day or total_elements > self.max_items_per_day:
            raise RuntimeError(f"{SOURCE} PVL daily result exceeds configured hard limits; cursor not advanced")
        return payload

    def _fetch_day(self, day):
        first = self._get_page(day, 0)
        total_pages = int(first.get("totalPages") or 0)
        total_elements = int(first.get("totalElements") or 0)
        if total_pages == 0:
            if first.get("content") or total_elements:
                raise RuntimeError(f"{SOURCE} PVL empty-page metadata mismatch; cursor not advanced")
            return []

        rows = []
        seen_notices = set()
        for page in range(total_pages):
            payload = first if page == 0 else self._get_page(day, page)
            if int(payload.get("totalPages") or 0) != total_pages:
                raise RuntimeError(f"{SOURCE} PVL pagination changed during day scan; cursor not advanced")
            for row in payload.get("content") or []:
                if not isinstance(row, dict):
                    raise RuntimeError(f"{SOURCE} PVL content contains non-object row; cursor not advanced")
                notice_id = _text(row.get("idAvviso"))
                if not notice_id:
                    # Non-procurement noise can be skipped only if it has no Works lot.
                    if any(_text(lot.get("natura_principale")).casefold() == "lavori" for lot in _lots(row)):
                        raise RuntimeError(f"{SOURCE} PVL Works row missing idAvviso; cursor not advanced")
                    continue
                if notice_id in seen_notices:
                    raise RuntimeError(f"{SOURCE} PVL pagination returned duplicate idAvviso; cursor not advanced")
                seen_notices.add(notice_id)
                rows.append(row)
        if len(rows) != total_elements:
            raise RuntimeError(
                f"{SOURCE} PVL pagination count mismatch expected={total_elements} returned={len(rows)}; cursor not advanced"
            )
        return rows

    @staticmethod
    def _apply_events(events, tracked, closed):
        for event in sorted(events, key=_event_key):
            external_id = _text(event.get("external_id"))
            if not external_id:
                raise RuntimeError(f"{SOURCE} event missing CIG identity; cursor not advanced")
            current = tracked.get(external_id)
            if current is None:
                current = closed.get(external_id)
            if current is not None and _event_key(event) <= _event_key(current):
                continue

            if not event.get("is_works"):
                if current is None:
                    continue
                state = _merge_state(current, event)
                state["closed_status"] = "not_construction"
                state["closed_reason"] = "latest PVL lot version no longer reports natura_principale=Lavori"
                tracked.pop(external_id, None)
                closed[external_id] = state
                continue

            if not event.get("active") or event.get("obscured"):
                if current is None:
                    continue
                state = _merge_state(current, event)
                state["closed_status"] = "publisher_inactive" if not event.get("active") else "publisher_obscured"
                state["closed_reason"] = "latest PVL version is no longer an active visible tender notice"
                tracked.pop(external_id, None)
                closed[external_id] = state
                continue

            tracked[external_id] = _merge_state(current, event)
            closed.pop(external_id, None)

    @staticmethod
    def _finalize(tracked, closed, *, now):
        observations, survivors = [], {}
        current = _dt(now) or datetime.now(timezone.utc)

        for state in closed.values():
            if state.get("was_visible"):
                observations.append(_observation(
                    state,
                    actionable=False,
                    lifecycle_status=_text(state.get("closed_status")) or "publisher_inactive",
                    lifecycle_reason=_text(state.get("closed_reason")) or "publisher no longer reports an actionable Works lot",
                    lifecycle_only=True,
                ))

        for external_id, state in tracked.items():
            deadline = _dt(state.get("deadline"))
            if deadline is not None and deadline > current:
                state["was_visible"] = True
                survivors[external_id] = state
                observations.append(_observation(
                    state,
                    actionable=True,
                    lifecycle_status="active",
                    lifecycle_reason="PVL reports active visible Lavori lot with future submission deadline",
                ))
                continue
            if deadline is None:
                if state.get("was_visible"):
                    observations.append(_observation(
                        state,
                        actionable=False,
                        lifecycle_status="deadline_missing",
                        lifecycle_reason="PVL Works lot no longer has a valid structured submission deadline",
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
                    lifecycle_reason="PVL lot submission deadline has elapsed",
                    lifecycle_only=True,
                ))
        return observations, survivors

    def fetch_incremental(self, *, watermark=None, now=None):
        current = _dt(now) or datetime.now(timezone.utc)
        target = self._target_day(current)
        cursor = ANACPVLCursor.decode(watermark) if watermark else None
        tracked = deepcopy(cursor.tracked) if cursor else {}
        closed = deepcopy(cursor.closed) if cursor else {}

        if cursor:
            completed = _day(cursor.completed_through, label="completed_through")
            if completed > target:
                raise RuntimeError(f"{SOURCE} cursor is ahead of current PVL day; cursor not advanced")
            start = completed + timedelta(days=1) - timedelta(days=self.overlap_days)
        else:
            completed = target - timedelta(days=self.initial_lookback_days)
            start = completed + timedelta(days=1)

        days = []
        day = start
        while day <= target and len(days) < self.max_days_per_sync:
            days.append(day)
            day += timedelta(days=1)

        for pub_day in days:
            events = []
            for payload in self._fetch_day(pub_day):
                events.extend(_notice_events(payload, publication_day=pub_day.isoformat()))
            self._apply_events(events, tracked, closed)
            if pub_day > completed:
                completed = pub_day

        if completed >= target:
            observations, tracked = self._finalize(tracked, closed, now=current)
            closed = {}
        else:
            # Do not publish intermediate truth during a long catch-up. A later
            # PVL rectification inside the remaining window may change the state.
            observations = []

        return observations, ANACPVLCursor(completed.isoformat(), tracked, closed).encode()


def build_italy_anac_pvl_connector(*, session=None, **kwargs):
    return ANACPVLConnector(session=session, **kwargs)


def fetch_italy_anac_tenders(*, watermark=None, now=None, connector=None):
    client = connector or build_italy_anac_pvl_connector()
    return client.fetch_incremental(watermark=watermark, now=now)
