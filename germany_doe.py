"""Germany DÖE/Bekanntmachungsservice daily Open Data connector.

The federal Open Data API publishes complete daily notice-version ZIP exports.
Production ingests only fully elapsed Europe/Berlin publication days. OCDS is
used as the cheap publisher-native discovery layer (including ``works`` and
lifecycle tags); the official ``format=domain`` detail is hydrated only when a
Works event can affect a tracked opportunity.

Commercial identity is procedure + lot. Notice UUID/version is publication
identity. This distinction is essential because a corrected competition notice
may receive a new notice UUID while retaining the same ``procedureIdentifier``.
Award and contract-modification notices are lifecycle signals only; they never
become standalone commercial opportunities.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import io
import json
import re
import zipfile
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests


SOURCE = "SERVICE_BUND_DE"
COUNTRY = "DEU"
EXPORT_URL = "https://oeffentlichevergabe.de/api/notice-exports"
DETAIL_BASE = "https://oeffentlichevergabe.de/api/notices"
HUMAN_BASE = "https://oeffentlichevergabe.de/ui/de/notices"
OPEN_DATA_POLICY = "https://oeffentlichevergabe.de/ui/de/Open-Data-Richtlinie"
ATTRIBUTION = "Datenservice Öffentlicher Einkauf / Bekanntmachungsservice"
DATASET = "Bekanntmachungsservice Open Data"
LICENSE = "CC0-1.0"
BERLIN = ZoneInfo("Europe/Berlin")
HEADERS = {
    "Accept": "*/*",
    "User-Agent": "ObraSignal Germany DÖE connector/1.0 (+official public-data ingestion)",
}


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
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z") if parsed else ""


def _day(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = _text(value)
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _last_complete_day(now=None):
    current = _dt(now) or datetime.now(timezone.utc)
    return current.astimezone(BERLIN).date() - timedelta(days=1)


def _human_url(notice_id):
    value = _text(notice_id)
    return f"{HUMAN_BASE}/{quote(value, safe='')}" if value else ""


def _localized(value, preferred="DEU"):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        if "value" in value:
            return _text(value.get("value"))
        return ""
    if not isinstance(value, list):
        return ""
    rows = [row for row in value if isinstance(row, dict)]
    for row in rows:
        if _text(row.get("languageId")).upper() == preferred:
            return _text(row.get("value"))
    for row in rows:
        result = _text(row.get("value"))
        if result:
            return result
    return ""


def _code(value, *, list_name=None):
    if not isinstance(value, dict):
        return ""
    if list_name and _text(value.get("listName")).lower() != list_name.lower():
        return ""
    return _text(value.get("value"))


def _cpvs(classification):
    if not isinstance(classification, dict):
        return []
    values = []
    primary = classification.get("mainClassificationCode")
    additions = classification.get("additionalClassificationCode")
    candidates = [primary] + (additions if isinstance(additions, list) else [])
    for row in candidates:
        code = _code(row, list_name="cpv")
        if code and code not in values:
            values.append(code)
    return values


def _bulk_place(release):
    tender = release.get("tender") if isinstance(release, dict) and isinstance(release.get("tender"), dict) else {}
    items = tender.get("items") if isinstance(tender.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        addresses = item.get("deliveryAddresses")
        if not isinstance(addresses, list):
            address = item.get("deliveryAddress")
            addresses = [address] if isinstance(address, dict) else []
        for address in addresses:
            if not isinstance(address, dict):
                continue
            parts = []
            for key in ("locality", "region", "postalCode", "countryName"):
                value = address.get(key)
                text = _localized(value) if isinstance(value, (dict, list)) else _text(value)
                if text and text not in parts:
                    parts.append(text)
            if parts:
                return " | ".join(parts)
    return ""


def _buyer(release):
    if not isinstance(release, dict):
        return ""
    buyer = release.get("buyer")
    if isinstance(buyer, dict):
        return _text(buyer.get("name"))
    return ""


def _tags(release):
    value = release.get("tag") if isinstance(release, dict) else None
    if isinstance(value, list):
        return tuple(_text(item).lower() for item in value if _text(item))
    return (_text(value).lower(),) if _text(value) else ()


def _file_identity(name):
    base = re.sub(r"\.json$", "", name.rsplit("/", 1)[-1], flags=re.I)
    match = re.fullmatch(r"(.+)-(\d+)", base)
    if not match:
        raise RuntimeError(f"{SOURCE} malformed notice-version filename; cursor not advanced")
    return match.group(1), int(match.group(2))


def _procedure_from_ocid(value):
    text = _text(value)
    prefix = "ocds-mnwr74-"
    return text[len(prefix):] if text.startswith(prefix) else ""


def _state_key(procedure_id, lot_id):
    return f"{procedure_id}:lot:{lot_id}"


def _deepcopy(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


@dataclass
class DOECursor:
    completed_day: str
    target_day: str
    tracked: dict
    closed: dict

    def encode(self):
        return json.dumps(
            {
                "version": 1,
                "completed_day": self.completed_day,
                "target_day": self.target_day,
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
        try:
            payload = json.loads(str(value))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid {SOURCE} cursor JSON") from exc
        if not isinstance(payload, dict) or int(payload.get("version") or 1) != 1:
            raise RuntimeError(f"invalid {SOURCE} cursor version")
        completed = _day(payload.get("completed_day"))
        target = _day(payload.get("target_day"))
        tracked = payload.get("tracked") or {}
        closed = payload.get("closed") or {}
        if not completed or not target or completed > target:
            raise RuntimeError(f"invalid {SOURCE} cursor day state")
        if not isinstance(tracked, dict) or not isinstance(closed, dict):
            raise RuntimeError(f"invalid {SOURCE} cursor lifecycle state")
        return cls(completed.isoformat(), target.isoformat(), tracked, closed)


class GermanyDOEConnector:
    def __init__(
        self,
        *,
        session=None,
        initial_lookback_days=30,
        max_days_per_sync=5,
        max_zip_bytes=64 * 1024 * 1024,
        max_uncompressed_bytes=256 * 1024 * 1024,
        max_entries_per_day=10_000,
        max_events_per_day=20_000,
        max_detail_hydrations=1_500,
        timeout=90,
    ):
        self.session = session or requests.Session()
        self.initial_lookback_days = max(1, int(initial_lookback_days))
        self.max_days_per_sync = max(1, int(max_days_per_sync))
        self.max_zip_bytes = max(1, int(max_zip_bytes))
        self.max_uncompressed_bytes = max(1, int(max_uncompressed_bytes))
        self.max_entries_per_day = max(1, int(max_entries_per_day))
        self.max_events_per_day = max(1, int(max_events_per_day))
        self.max_detail_hydrations = max(1, int(max_detail_hydrations))
        self.timeout = int(timeout)
        self._detail_count = 0

    def _request(self, url, *, params=None, stream=False, accept="*/*"):
        response = self.session.get(
            url,
            params=params,
            headers={**HEADERS, "Accept": accept},
            timeout=self.timeout,
            stream=stream,
        )
        if getattr(response, "status_code", None) != 200:
            raise RuntimeError(f"{SOURCE} HTTP {getattr(response, 'status_code', 'unknown')}; cursor not advanced")
        return response

    def _read_bounded(self, response):
        chunks, total = [], 0
        iterator = response.iter_content(1024 * 1024) if hasattr(response, "iter_content") else [response.content]
        for chunk in iterator:
            if not chunk:
                continue
            total += len(chunk)
            if total > self.max_zip_bytes:
                raise RuntimeError(f"{SOURCE} daily ZIP exceeds max_zip_bytes; cursor not advanced")
            chunks.append(chunk)
        return b"".join(chunks)

    def _download_day(self, pub_day):
        response = self._request(
            EXPORT_URL,
            params={"pubDay": pub_day.isoformat(), "format": "ocds.zip"},
            stream=True,
        )
        blob = self._read_bounded(response)
        if blob[:4] != b"PK\x03\x04":
            raise RuntimeError(f"{SOURCE} daily export is not a ZIP; cursor not advanced")
        try:
            archive = zipfile.ZipFile(io.BytesIO(blob))
        except zipfile.BadZipFile as exc:
            raise RuntimeError(f"{SOURCE} daily export is malformed; cursor not advanced") from exc
        infos = [info for info in archive.infolist() if not info.is_dir() and info.filename.lower().endswith(".json")]
        if len(infos) > self.max_entries_per_day:
            raise RuntimeError(f"{SOURCE} daily export exceeds max_entries_per_day; cursor not advanced")
        if sum(max(0, int(info.file_size)) for info in infos) > self.max_uncompressed_bytes:
            raise RuntimeError(f"{SOURCE} daily export exceeds uncompressed hard limit; cursor not advanced")

        events, seen_versions = [], set()
        for info in infos:
            notice_id, version = _file_identity(info.filename)
            identity = (notice_id, version)
            if identity in seen_versions:
                raise RuntimeError(f"{SOURCE} duplicate notice-version in daily export; cursor not advanced")
            seen_versions.add(identity)
            try:
                package = json.loads(archive.read(info))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise RuntimeError(f"{SOURCE} malformed OCDS JSON; cursor not advanced") from exc
            releases = package.get("releases") if isinstance(package, dict) else None
            if not isinstance(releases, list):
                raise RuntimeError(f"{SOURCE} OCDS package missing releases; cursor not advanced")
            for release in releases:
                if not isinstance(release, dict):
                    raise RuntimeError(f"{SOURCE} OCDS release is malformed; cursor not advanced")
                events.append((release, notice_id, version))
                if len(events) > self.max_events_per_day:
                    raise RuntimeError(f"{SOURCE} daily export exceeds max_events_per_day; cursor not advanced")
        return sorted(events, key=self._event_key)

    @staticmethod
    def _event_key(event):
        release, notice_id, version = event
        stamp = _dt(release.get("date")) or datetime.min.replace(tzinfo=timezone.utc)
        return stamp, notice_id, int(version)

    def _detail(self, notice_id):
        self._detail_count += 1
        if self._detail_count > self.max_detail_hydrations:
            raise RuntimeError(f"{SOURCE} exceeded max_detail_hydrations; cursor not advanced")
        response = self._request(
            f"{DETAIL_BASE}/{quote(_text(notice_id), safe='')}",
            params={"format": "domain"},
            accept="application/json",
        )
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError(f"{SOURCE} domain detail is not JSON; cursor not advanced") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"{SOURCE} domain detail is malformed; cursor not advanced")
        return payload

    @staticmethod
    def _procedure_hint(release):
        tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
        return _text(tender.get("id")) or _procedure_from_ocid(release.get("ocid"))

    @staticmethod
    def _is_works(release):
        tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
        return _text(tender.get("mainProcurementCategory")).lower() == "works"

    @staticmethod
    def _bulk_lot_map(release):
        tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
        lots = tender.get("lots") if isinstance(tender.get("lots"), list) else []
        return {_text(lot.get("id")): lot for lot in lots if isinstance(lot, dict) and _text(lot.get("id"))}

    def _state_from_lot(self, release, detail, lot, *, notice_id, version, previous=None):
        purpose = detail.get("purpose") if isinstance(detail.get("purpose"), dict) else {}
        if _code(purpose.get("mainNature"), list_name="contract-nature").lower() != "works":
            raise RuntimeError(f"{SOURCE} bulk/detail construction semantics disagree; cursor not advanced")
        procedure_id = _text(detail.get("procedureIdentifier")) or self._procedure_hint(release)
        lot_id = _text(lot.get("id"))
        if not procedure_id or not lot_id:
            raise RuntimeError(f"{SOURCE} Works detail missing procedure/lot identity; cursor not advanced")

        terms = lot.get("submissionTerms") if isinstance(lot.get("submissionTerms"), dict) else {}
        tender_deadline = _utc(terms.get("deadlineReceiptTenders"))
        request_deadline = _utc(terms.get("deadlineReceiptRequests"))
        deadline = tender_deadline or request_deadline
        deadline_kind = "tender" if tender_deadline else ("request" if request_deadline else "")
        cpvs = _cpvs(lot.get("classification"))
        if not cpvs:
            cpvs = _cpvs(detail.get("classification"))

        bulk_tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
        bulk_lot = self._bulk_lot_map(release).get(lot_id) or {}
        title = _localized(lot.get("title")) or _text(bulk_lot.get("title")) or _localized(purpose.get("title")) or _text(bulk_tender.get("title"))
        description = _localized(lot.get("description")) or _localized(purpose.get("description")) or title
        procedure = detail.get("procedure") if isinstance(detail.get("procedure"), dict) else {}
        procedure_type = _code(procedure.get("procedureType"), list_name="procurement-procedure-type")
        publication = _utc(detail.get("publicationDate")) or _utc(release.get("date"))
        updated = _utc(detail.get("changeDate")) or publication
        if not publication:
            raise RuntimeError(f"{SOURCE} Works detail missing publication timestamp; cursor not advanced")

        prior = previous if isinstance(previous, dict) else {}
        return {
            "procedure_id": procedure_id,
            "lot_id": lot_id,
            "title": title,
            "description": description,
            "buyer": _buyer(release) or _text(prior.get("buyer")),
            "place": _bulk_place(release) or _text(prior.get("place")),
            "cpv_codes": cpvs,
            "deadline": deadline,
            "deadline_kind": deadline_kind,
            "published_at": publication,
            "source_updated_at": updated,
            "notice_id": _text(detail.get("noticeIdentifier")) or notice_id,
            "original_notice_id": _text(detail.get("originalNoticeIdentifier")),
            "notice_version": _text(detail.get("noticeVersion")) or f"{version:02d}",
            "notice_type": _code(detail.get("noticeType")),
            "notice_subtype": _code(detail.get("noticeSubType")),
            "procedure_type": procedure_type,
            "submission_url": _text(terms.get("submissionUrl")),
            "was_visible": bool(prior.get("was_visible")),
            "dirty": True,
        }

    def _apply_tender(self, release, notice_id, version, tracked, closed):
        detail = self._detail(notice_id)
        procedure_id = _text(detail.get("procedureIdentifier")) or self._procedure_hint(release)
        if not procedure_id:
            raise RuntimeError(f"{SOURCE} tender detail missing procedureIdentifier; cursor not advanced")
        notice_type = detail.get("noticeType") if isinstance(detail.get("noticeType"), dict) else {}
        if _text(notice_type.get("listName")).lower() != "competition":
            raise RuntimeError(f"{SOURCE} tender tag does not resolve to competition detail; cursor not advanced")
        lots = detail.get("lots") if isinstance(detail.get("lots"), list) else None
        if not lots:
            raise RuntimeError(f"{SOURCE} Works tender has no structured lots; cursor not advanced")
        seen = set()
        for lot in lots:
            if not isinstance(lot, dict) or not _text(lot.get("id")):
                raise RuntimeError(f"{SOURCE} Works tender contains malformed lot; cursor not advanced")
            lot_id = _text(lot.get("id"))
            if lot_id in seen:
                raise RuntimeError(f"{SOURCE} Works tender contains duplicate lot; cursor not advanced")
            seen.add(lot_id)
            key = _state_key(procedure_id, lot_id)
            state = self._state_from_lot(release, detail, lot, notice_id=notice_id, version=version, previous=tracked.get(key))
            tracked[key] = state
            closed.pop(key, None)

    def _close_procedure(self, release, notice_id, *, tracked, closed, status, reason, require_terminal_detail=True):
        procedure_hint = self._procedure_hint(release)
        candidates = [key for key, state in tracked.items() if _text(state.get("procedure_id")) == procedure_hint]
        if not candidates:
            return
        detail = self._detail(notice_id)
        procedure_id = _text(detail.get("procedureIdentifier")) or procedure_hint
        notice_type = detail.get("noticeType") if isinstance(detail.get("noticeType"), dict) else {}
        list_name = _text(notice_type.get("listName")).lower()
        value = _text(notice_type.get("value")).lower()
        if require_terminal_detail and list_name not in {"result", "cont-modif"} and value not in {"can-standard", "can-modif"}:
            return
        lot_ids = {
            _text(lot.get("id")) for lot in (detail.get("lots") or [])
            if isinstance(lot, dict) and _text(lot.get("id"))
        }
        matched = []
        for key in list(tracked):
            state = tracked[key]
            if _text(state.get("procedure_id")) != procedure_id:
                continue
            if lot_ids and _text(state.get("lot_id")) not in lot_ids:
                continue
            matched.append(key)
        if not matched and not lot_ids:
            matched = [key for key, state in tracked.items() if _text(state.get("procedure_id")) == procedure_id]
        for key in matched:
            state = tracked.pop(key)
            state["terminal_status"] = status
            state["terminal_reason"] = reason
            state["notice_id"] = _text(detail.get("noticeIdentifier")) or notice_id
            state["original_notice_id"] = _text(detail.get("originalNoticeIdentifier")) or _text(state.get("original_notice_id"))
            state["notice_version"] = _text(detail.get("noticeVersion")) or _text(state.get("notice_version"))
            state["notice_type"] = _code(detail.get("noticeType"))
            state["notice_subtype"] = _code(detail.get("noticeSubType"))
            state["source_updated_at"] = _utc(detail.get("changeDate")) or _utc(detail.get("publicationDate")) or _text(state.get("source_updated_at"))
            closed[key] = state

    def _process_day(self, pub_day, tracked, closed):
        for release, notice_id, version in self._download_day(pub_day):
            if not self._is_works(release):
                continue
            tags = set(_tags(release))
            if "tender" in tags:
                self._apply_tender(release, notice_id, version, tracked, closed)
                continue
            if "award" in tags:
                self._close_procedure(
                    release,
                    notice_id,
                    tracked=tracked,
                    closed=closed,
                    status="award_published",
                    reason="publisher reports a result/award notice for this Works lot",
                )
                continue
            if "planning" in tags:
                continue
            # Live validation found untagged Works as contract-modification notices
            # (noticeType cont-modif / can-modif). Hydrate only when a procedure is
            # currently tracked; unknown untagged publications cannot create an
            # opportunity and therefore need no network request.
            procedure_hint = self._procedure_hint(release)
            if procedure_hint and any(_text(state.get("procedure_id")) == procedure_hint for state in tracked.values()):
                self._close_procedure(
                    release,
                    notice_id,
                    tracked=tracked,
                    closed=closed,
                    status="contract_modified",
                    reason="publisher reports a post-award contract modification",
                )

    @staticmethod
    def _observation(state, *, actionable, lifecycle_status, lifecycle_reason, lifecycle_only=False):
        cpvs = [_text(code) for code in state.get("cpv_codes", []) if _text(code)]
        primary = cpvs[0] if cpvs else ""
        key = _state_key(_text(state.get("procedure_id")), _text(state.get("lot_id")))
        record = {
            "source": SOURCE,
            "external_id": key,
            "title": _text(state.get("title")),
            "description": _text(state.get("description")) or _text(state.get("title")),
            "buyer": _text(state.get("buyer")),
            "country": COUNTRY,
            "cpv": primary,
            "taxonomy": "CPV" if primary else "",
            "category_code": primary,
            "cpv_codes": cpvs,
            "cpv_classifications": [{"id": code} for code in cpvs],
            "value": "",
            "currency": "",
            "deadline": _text(state.get("deadline")),
            "deadline_kind": _text(state.get("deadline_kind")),
            "publication_date": _text(state.get("published_at"))[:10],
            "published_at": _text(state.get("published_at")) or None,
            "source_updated_at": _text(state.get("source_updated_at")) or None,
            "url": _human_url(state.get("notice_id")),
            "submission_url": _text(state.get("submission_url")),
            "market": "GLOBAL",
            "place": _text(state.get("place")),
            "source_status": _text(state.get("notice_type")),
            "source_phase": _text(state.get("notice_type")),
            "signal_type": "TENDER",
            "procurement_method": _text(state.get("procedure_type")),
            "contract_type": "works",
            "source_reference": _text(state.get("notice_id")),
            "procedure_identifier": _text(state.get("procedure_id")),
            "lot_identifier": _text(state.get("lot_id")),
            "notice_identifier": _text(state.get("notice_id")),
            "original_notice_identifier": _text(state.get("original_notice_id")),
            "notice_version": _text(state.get("notice_version")),
            "notice_subtype": _text(state.get("notice_subtype")),
            "ocid": f"ocds-mnwr74-{_text(state.get('procedure_id'))}",
            "attribution": ATTRIBUTION,
            "source_dataset": DATASET,
            "source_api_url": EXPORT_URL,
            "reuse_information": OPEN_DATA_POLICY,
            "license": LICENSE,
            "source_modified": True,
            "is_actionable": bool(actionable),
            "lifecycle_status": lifecycle_status,
            "lifecycle_reason": lifecycle_reason,
        }
        if lifecycle_only or not actionable:
            record["_lifecycle_only"] = True
        return record

    def _finalize(self, tracked, closed, *, now):
        observations, survivors = [], {}
        for state in closed.values():
            if state.get("was_visible"):
                observations.append(self._observation(
                    state,
                    actionable=False,
                    lifecycle_status=_text(state.get("terminal_status")) or "closed",
                    lifecycle_reason=_text(state.get("terminal_reason")) or "publisher reports terminal lifecycle state",
                    lifecycle_only=True,
                ))

        for key, state in tracked.items():
            deadline = _dt(state.get("deadline"))
            if deadline and deadline > now:
                if state.get("dirty") or not state.get("was_visible"):
                    observations.append(self._observation(
                        state,
                        actionable=True,
                        lifecycle_status="active",
                        lifecycle_reason="publisher reports a Works lot with a future submission deadline",
                    ))
                state["was_visible"] = True
                state["dirty"] = False
                survivors[key] = state
                continue
            if deadline is None:
                if state.get("was_visible"):
                    observations.append(self._observation(
                        state,
                        actionable=False,
                        lifecycle_status="deadline_missing",
                        lifecycle_reason="Works lot no longer has a valid structured submission deadline",
                        lifecycle_only=True,
                    ))
                state["was_visible"] = False
                state["dirty"] = False
                survivors[key] = state
                continue
            if state.get("was_visible"):
                observations.append(self._observation(
                    state,
                    actionable=False,
                    lifecycle_status="deadline_elapsed",
                    lifecycle_reason="submission deadline has elapsed",
                    lifecycle_only=True,
                ))
        return observations, survivors

    def fetch_incremental(self, *, watermark=None, now=None):
        self._detail_count = 0
        current = _dt(now) or datetime.now(timezone.utc)
        last_complete = _last_complete_day(current)
        cursor = DOECursor.decode(watermark) if watermark else None

        if cursor:
            completed = _day(cursor.completed_day)
            target = _day(cursor.target_day)
            if not completed or not target:
                raise RuntimeError(f"invalid {SOURCE} cursor day state")
            if target > last_complete or completed > last_complete:
                raise RuntimeError(f"{SOURCE} cursor points into the future; cursor not advanced")
            tracked = _deepcopy(cursor.tracked)
            closed = _deepcopy(cursor.closed)
            if completed >= target and target < last_complete:
                target = last_complete
        else:
            target = last_complete
            completed = target - timedelta(days=self.initial_lookback_days)
            tracked, closed = {}, {}

        processed = 0
        next_day = completed + timedelta(days=1)
        while next_day <= target and processed < self.max_days_per_sync:
            self._process_day(next_day, tracked, closed)
            completed = next_day
            next_day += timedelta(days=1)
            processed += 1

        caught_up = completed >= target
        if caught_up:
            observations, tracked = self._finalize(tracked, closed, now=current)
            closed = {}
        else:
            # Do not expose an intermediate historical state. A later day in the
            # frozen catch-up horizon may contain a correction, award or contract
            # modification that changes what is commercially true now.
            observations = []

        next_cursor = DOECursor(completed.isoformat(), target.isoformat(), tracked, closed).encode()
        return observations, next_cursor


def build_germany_doe_connector(*, session=None, **kwargs):
    return GermanyDOEConnector(session=session, **kwargs)


def fetch_germany_doe_tenders(*, watermark=None, now=None, connector=None):
    client = connector or build_germany_doe_connector()
    return client.fetch_incremental(watermark=watermark, now=now)
