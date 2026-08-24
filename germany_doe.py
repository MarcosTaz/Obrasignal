"""Germany DOE/Bekanntmachungsservice public eForms daily-bulk connector.

The German Public Procurement Data Service exposes the official Open Data API
without authentication.  Its ``/api/notice-exports`` endpoint exports notices
by *publication archive day* (``pubDay``) and does not allow the current day.
Live validation on 2026-08-24 established that archive-day and eForms
``IssueDate`` are not interchangeable: the 2026-08-23 archive contained notices
with IssueDate 2026-08-21.  Therefore durable progress is keyed only by the
publisher's closed ``pubDay`` partitions; IssueDate/IssueTime remain document
metadata and an intra-day tie-breaker.

Production consumes the publisher-original eForms ZIP, not HTML/PDF scraping or
the transformed OCDS export.  Only publisher-native
``ProcurementTypeCode=works`` ContractNotice records can create opportunities.
Identity is lot-level (ContractFolderID + lot ID), because deadlines and CPVs can
differ by lot.  ContractAwardNotice records are used only to close tracked
opportunities; they are not exposed as an AWARD product signal.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
import json
import re
import zipfile
from xml.etree.ElementTree import ParseError, fromstring
from zoneinfo import ZoneInfo

import requests


SOURCE = "SERVICE_BUND_DE"
COUNTRY = "DEU"
DOE_BASE = "https://oeffentlichevergabe.de"
DOE_EXPORTS = f"{DOE_BASE}/api/notice-exports"
DOE_HUMAN = f"{DOE_BASE}/ui/de/notices/{{notice_id}}"
DOE_POLICY = f"{DOE_BASE}/documentation/api/opendata"
DOE_ATTRIBUTION = "Datenservice Öffentlicher Einkauf — Bekanntmachungsservice, Deutschland"
DOE_DATASET = "Bekanntmachungsservice OpenData — original eForms daily exports"
DOE_EFORMS_ACCEPT = "application/vnd.bekanntmachungsservice.eforms.zip+zip"
DOE_HEADERS = {
    "Accept": DOE_EFORMS_ACCEPT,
    "User-Agent": "ObraSignal Germany DOE connector/1.0 (+official CC0 open-data ingestion)",
}
BERLIN = ZoneInfo("Europe/Berlin")
_FILE_RE = re.compile(r"^(?P<notice>[0-9a-fA-F-]{36})-(?P<version>\d+)\.xml$")


def _local(tag):
    return str(tag).rsplit("}", 1)[-1]


def _text(elem):
    return "" if elem is None or elem.text is None else " ".join(str(elem.text).split())


def _direct(elem, name):
    if elem is None:
        return None
    for child in list(elem):
        if _local(child.tag) == name:
            return child
    return None


def _direct_text(elem, name):
    return _text(_direct(elem, name))


def _path(elem, *names):
    current = elem
    for name in names:
        current = _direct(current, name)
        if current is None:
            return None
    return current


def _path_text(elem, *names):
    return _text(_path(elem, *names))


def _first_desc(elem, name):
    if elem is None:
        return None
    for child in elem.iter():
        if child is not elem and _local(child.tag) == name:
            return child
    return None


def _descendants(elem, name):
    if elem is None:
        return []
    return [child for child in elem.iter() if child is not elem and _local(child.tag) == name]


def _parse_source_datetime(value):
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


def _parse_issue(date_value, time_value):
    date_text = str(date_value or "").strip()
    time_text = str(time_value or "").strip()
    if not date_text or not time_text:
        return None
    date_core = date_text[:10]
    if len(date_core) != 10:
        return None
    if time_text.endswith("Z") or (
        len(time_text) >= 6 and time_text[-6] in "+-" and time_text[-3] == ":"
    ):
        stamp = f"{date_core}T{time_text}"
    else:
        stamp = f"{date_core}T{time_text}{date_text[10:]}"
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BERLIN)
    return parsed.astimezone(timezone.utc)


def _utc(value):
    parsed = _parse_source_datetime(value)
    if parsed is None:
        return None
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_day(value, *, label="day"):
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise RuntimeError(f"invalid {SOURCE} cursor {label}") from exc


def _issue_timestamp(root):
    return _parse_issue(_direct_text(root, "IssueDate"), _direct_text(root, "IssueTime"))


def _cpvs(elem):
    out = []
    for child in elem.iter() if elem is not None else ():
        if _local(child.tag) != "ItemClassificationCode":
            continue
        list_name = str(child.attrib.get("listName") or "").strip().lower()
        if list_name and list_name != "cpv":
            continue
        value = _text(child)
        if value and value not in out:
            out.append(value)
    return out


def _organization_map(root):
    organizations = _first_desc(root, "Organizations")
    out = {}
    if organizations is None:
        return out
    for organization in list(organizations):
        if _local(organization.tag) != "Organization":
            continue
        company = _direct(organization, "Company")
        org_id = _path_text(company, "PartyIdentification", "ID")
        if not org_id:
            continue
        address = _direct(company, "PostalAddress")
        out[org_id] = {
            "name": _path_text(company, "PartyName", "Name"),
            "city": _direct_text(address, "CityName"),
            "nuts": _direct_text(address, "CountrySubentityCode"),
            "country": _path_text(address, "Country", "IdentificationCode"),
        }
    return out


def _buyer(root):
    contracting = _first_desc(root, "ContractingParty")
    party = _direct(contracting, "Party") if contracting is not None else None
    buyer_ref = _path_text(party, "PartyIdentification", "ID")
    return _organization_map(root).get(buyer_ref, {})


def _project(root):
    return _first_desc(root, "ProcurementProject")


def _project_place(project, buyer_info):
    location = _direct(project, "RealizedLocation") if project is not None else None
    description = _direct_text(location, "Description")
    address = _direct(location, "Address") if location is not None else None
    nuts = _direct_text(address, "CountrySubentityCode")
    country = _path_text(address, "Country", "IdentificationCode")
    values = []
    for value in (description, nuts, country):
        if value and value not in values:
            values.append(value)
    if not values:
        for key in ("city", "nuts", "country"):
            value = str(buyer_info.get(key) or "").strip()
            if value and value not in values:
                values.append(value)
    return " | ".join(values)


def _amount(elem):
    for name in ("EstimatedOverallContractAmount", "TaxExclusiveAmount"):
        child = _first_desc(elem, name)
        if child is not None and _text(child):
            return _text(child), str(child.attrib.get("currencyID") or "").strip()
    return "", ""


def _lot_deadline(lot):
    process = _direct(lot, "TenderingProcess")
    period = _direct(process, "TenderSubmissionDeadlinePeriod") if process is not None else None
    if period is None:
        return ""
    return _utc(_parse_issue(_direct_text(period, "EndDate"), _direct_text(period, "EndTime"))) or ""


def _notice_lots(root):
    return [child for child in root.iter() if _local(child.tag) == "ProcurementProjectLot"]


def _human_url(notice_id):
    value = str(notice_id or "").strip()
    return DOE_HUMAN.format(notice_id=value) if value else ""


def _file_identity(name):
    match = _FILE_RE.fullmatch(str(name or ""))
    if not match:
        raise RuntimeError(f"{SOURCE} eForms ZIP contains unsupported filename {name!r}; cursor not advanced")
    return match.group("notice"), int(match.group("version"))


def _notice_events(root, *, publication_day, filename_notice_id, file_version):
    if _local(root.tag) != "ContractNotice":
        return []
    project = _project(root)
    if _direct_text(project, "ProcurementTypeCode").lower() != "works":
        return []

    folder_id = _direct_text(root, "ContractFolderID")
    notice_id = _direct_text(root, "ID")
    issued = _issue_timestamp(root)
    if not folder_id or not notice_id or issued is None:
        raise RuntimeError(f"{SOURCE} Works notice missing ContractFolderID/ID/IssueDate+IssueTime; cursor not advanced")
    if notice_id != filename_notice_id:
        raise RuntimeError(f"{SOURCE} eForms filename/root notice ID mismatch; cursor not advanced")

    lots = _notice_lots(root)
    if not lots:
        raise RuntimeError(f"{SOURCE} Works notice contains no ProcurementProjectLot; cursor not advanced")

    buyer_info = _buyer(root)
    project_title = _direct_text(project, "Name")
    project_description = _direct_text(project, "Description")
    project_cpvs = _cpvs(project)
    place = _project_place(project, buyer_info)
    project_value, project_currency = _amount(project)
    process = _first_desc(root, "TenderingProcess")
    procedure_method = _direct_text(process, "ProcedureCode")
    notice_type = _direct_text(root, "NoticeTypeCode")
    issued_utc = _utc(issued)

    events = []
    for lot in lots:
        lot_id = _direct_text(lot, "ID")
        if not lot_id:
            raise RuntimeError(f"{SOURCE} Works lot missing ID; cursor not advanced")
        lot_name = _direct_text(lot, "Name")
        cpvs = _cpvs(lot) or project_cpvs
        lot_value, lot_currency = _amount(lot)
        if len(lots) > 1:
            suffix = lot_name or lot_id
            title = f"{project_title} — {suffix}" if project_title else suffix
        else:
            title = project_title or lot_name or lot_id
        events.append({
            "external_id": f"{folder_id}::{lot_id}",
            "procedure_id": folder_id,
            "lot_id": lot_id,
            "lot_count": len(lots),
            "notice_id": notice_id,
            "file_version": int(file_version),
            "publication_day": publication_day,
            "notice_type": notice_type,
            "event_kind": "notice",
            "closed": False,
            "title": title,
            "description": project_description or title,
            "buyer": str(buyer_info.get("name") or "").strip(),
            "place": place,
            "cpv_codes": cpvs,
            "deadline": _lot_deadline(lot),
            "value": lot_value or project_value,
            "currency": lot_currency or project_currency,
            "first_published_at": issued_utc,
            "source_updated_at": issued_utc,
            "url": _human_url(notice_id),
            "procurement_method": procedure_method,
            "was_visible": False,
        })
    return events


def _award_lot_ids(root):
    out = []
    for result in _descendants(root, "LotResult"):
        lot_id = _path_text(result, "TenderLot", "ID")
        if lot_id and lot_id not in out:
            out.append(lot_id)
    if out:
        return out
    for lot in _notice_lots(root):
        lot_id = _direct_text(lot, "ID")
        if lot_id and lot_id not in out:
            out.append(lot_id)
    return out


def _award_events(root, *, publication_day, filename_notice_id, file_version, tracked_folders=()):
    if _local(root.tag) != "ContractAwardNotice":
        return []
    project = _project(root)
    folder_id = _direct_text(root, "ContractFolderID")
    project_type = _direct_text(project, "ProcurementTypeCode").lower()
    if project_type != "works" and folder_id not in set(tracked_folders):
        return []

    notice_id = _direct_text(root, "ID")
    issued = _issue_timestamp(root)
    if not folder_id or not notice_id or issued is None:
        raise RuntimeError(f"{SOURCE} relevant award missing ContractFolderID/ID/IssueDate+IssueTime; cursor not advanced")
    if notice_id != filename_notice_id:
        raise RuntimeError(f"{SOURCE} award filename/root notice ID mismatch; cursor not advanced")
    lot_ids = _award_lot_ids(root)
    if not lot_ids:
        raise RuntimeError(f"{SOURCE} relevant award contains no lot identities; cursor not advanced")

    return [{
        "external_id": f"{folder_id}::{lot_id}",
        "procedure_id": folder_id,
        "lot_id": lot_id,
        "notice_id": notice_id,
        "file_version": int(file_version),
        "publication_day": publication_day,
        "notice_type": _direct_text(root, "NoticeTypeCode"),
        "event_kind": "award",
        "closed": True,
        "source_updated_at": _utc(issued),
        "was_visible": False,
    } for lot_id in lot_ids]


def _event_key(event):
    day = _parse_day(event.get("publication_day"), label="event publication_day")
    source_time = _parse_source_datetime(event.get("source_updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
    return (day, source_time, int(event.get("file_version") or 0), str(event.get("notice_id") or ""))


def _merge_event(current, incoming):
    if current is None:
        return deepcopy(incoming)
    if _event_key(incoming) < _event_key(current):
        return current
    visible = bool(current.get("was_visible")) or bool(incoming.get("was_visible"))
    if incoming.get("closed"):
        closed = deepcopy(current)
        closed.update({
            "notice_id": incoming.get("notice_id") or current.get("notice_id"),
            "file_version": incoming.get("file_version") or current.get("file_version"),
            "publication_day": incoming.get("publication_day") or current.get("publication_day"),
            "notice_type": incoming.get("notice_type") or current.get("notice_type"),
            "event_kind": "award",
            "closed": True,
            "source_updated_at": incoming.get("source_updated_at") or current.get("source_updated_at"),
            "url": _human_url(incoming.get("notice_id")) or current.get("url"),
            "was_visible": visible,
        })
        return closed
    updated = deepcopy(incoming)
    updated["was_visible"] = visible
    first_values = [
        str(value or "").strip()
        for value in (current.get("first_published_at"), incoming.get("first_published_at"))
        if str(value or "").strip()
    ]
    if first_values:
        updated["first_published_at"] = min(first_values)
    return updated


def _observation(state, *, actionable, lifecycle_status, lifecycle_reason, lifecycle_only=False):
    cpvs = [str(code).strip() for code in state.get("cpv_codes", []) if str(code).strip()]
    primary = cpvs[0] if cpvs else ""
    row = {
        "source": SOURCE,
        "external_id": str(state.get("external_id") or ""),
        "title": str(state.get("title") or ""),
        "description": str(state.get("description") or ""),
        "buyer": str(state.get("buyer") or ""),
        "country": COUNTRY,
        "cpv": primary,
        "taxonomy": "CPV" if primary else "",
        "category_code": primary,
        "cpv_codes": cpvs,
        "value": str(state.get("value") or ""),
        "currency": str(state.get("currency") or ""),
        "deadline": str(state.get("deadline") or ""),
        "publication_date": str(state.get("publication_day") or ""),
        "published_at": state.get("first_published_at") or None,
        "source_updated_at": state.get("source_updated_at") or None,
        "url": str(state.get("url") or ""),
        "market": "GLOBAL",
        "place": str(state.get("place") or ""),
        "source_status": str(state.get("notice_type") or state.get("event_kind") or ""),
        "source_phase": str(state.get("event_kind") or "notice"),
        "signal_type": "TENDER",
        "procurement_method": str(state.get("procurement_method") or ""),
        "contract_type": "works",
        "source_reference": str(state.get("notice_id") or ""),
        "notice_identifier": str(state.get("notice_id") or ""),
        "doe_contract_folder_id": str(state.get("procedure_id") or ""),
        "source_publication_day": str(state.get("publication_day") or ""),
        "lot_id": str(state.get("lot_id") or ""),
        "lot_count": int(state.get("lot_count") or 1),
        "attribution": DOE_ATTRIBUTION,
        "source_dataset": DOE_DATASET,
        "source_api_url": DOE_EXPORTS,
        "reuse_information": DOE_POLICY,
        "reuse_license": "CC0-1.0",
        "source_modified": True,
        "is_actionable": bool(actionable),
        "lifecycle_status": lifecycle_status,
        "lifecycle_reason": lifecycle_reason,
    }
    if lifecycle_only or not actionable:
        row["_lifecycle_only"] = True
    return row


@dataclass
class GermanDOECursor:
    completed_through: str
    tracked: dict
    closed: dict

    def encode(self):
        return json.dumps({
            "completed_through": self.completed_through,
            "tracked": self.tracked,
            "closed": self.closed,
        }, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    @classmethod
    def decode(cls, value):
        if not value:
            return None
        try:
            payload = json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"invalid {SOURCE} cursor JSON") from exc
        completed = str(payload.get("completed_through") or "").strip()
        tracked = payload.get("tracked") or {}
        closed = payload.get("closed") or {}
        _parse_day(completed, label="completed_through")
        if not isinstance(tracked, dict) or not isinstance(closed, dict):
            raise RuntimeError(f"invalid {SOURCE} cursor state")
        return cls(completed, tracked, closed)


class GermanDOEOpenDataConnector:
    def __init__(
        self,
        *,
        session=None,
        initial_lookback_days=60,
        overlap_days=1,
        max_days_per_sync=7,
        max_archive_bytes=32 * 1024 * 1024,
        max_entries=5000,
        max_entry_bytes=4 * 1024 * 1024,
        max_uncompressed_bytes=256 * 1024 * 1024,
        timeout=120,
    ):
        self.session = session or requests.Session()
        self.initial_lookback_days = max(1, int(initial_lookback_days))
        self.overlap_days = max(0, int(overlap_days))
        self.max_days_per_sync = max(1, int(max_days_per_sync))
        self.max_archive_bytes = max(1024, int(max_archive_bytes))
        self.max_entries = max(1, int(max_entries))
        self.max_entry_bytes = max(1024, int(max_entry_bytes))
        self.max_uncompressed_bytes = max(self.max_entry_bytes, int(max_uncompressed_bytes))
        self.timeout = max(1, int(timeout))

    @staticmethod
    def _target_day(now):
        current = _parse_source_datetime(now) or datetime.now(timezone.utc)
        return current.astimezone(BERLIN).date() - timedelta(days=1)

    def _download_day(self, day):
        response = self.session.get(
            DOE_EXPORTS,
            params={"pubDay": day.isoformat()},
            headers=DOE_HEADERS,
            timeout=self.timeout,
            stream=True,
            allow_redirects=True,
        )
        response.raise_for_status()
        body = bytearray()
        try:
            for chunk in response.iter_content(65536):
                if not chunk:
                    continue
                body.extend(chunk)
                if len(body) > self.max_archive_bytes:
                    raise RuntimeError(f"{SOURCE} daily ZIP exceeds max_archive_bytes; cursor not advanced")
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()
        data = bytes(body)
        if not data.startswith(b"PK"):
            raise RuntimeError(f"{SOURCE} daily export is not a ZIP archive; cursor not advanced")
        return data

    def _archive_events(self, day, data, *, tracked):
        try:
            zf = zipfile.ZipFile(BytesIO(data))
        except (zipfile.BadZipFile, OSError) as exc:
            raise RuntimeError(f"{SOURCE} invalid daily ZIP; cursor not advanced") from exc
        with zf:
            infos = zf.infolist()
            if len(infos) > self.max_entries:
                raise RuntimeError(f"{SOURCE} daily ZIP exceeds max_entries; cursor not advanced")
            names = [info.filename for info in infos if not info.is_dir()]
            if len(names) != len(set(names)):
                raise RuntimeError(f"{SOURCE} daily ZIP contains duplicate filenames; cursor not advanced")
            total = 0
            for info in infos:
                if info.is_dir():
                    continue
                if info.file_size > self.max_entry_bytes:
                    raise RuntimeError(f"{SOURCE} eForms entry exceeds max_entry_bytes; cursor not advanced")
                total += info.file_size
                if total > self.max_uncompressed_bytes:
                    raise RuntimeError(f"{SOURCE} daily ZIP exceeds max_uncompressed_bytes; cursor not advanced")

            tracked_folders = {
                str(state.get("procedure_id") or "")
                for state in tracked.values()
                if isinstance(state, dict) and str(state.get("procedure_id") or "")
            }
            events = []
            for info in infos:
                if info.is_dir():
                    continue
                filename_notice_id, file_version = _file_identity(info.filename)
                try:
                    root = fromstring(zf.read(info))
                except (ParseError, ValueError, OSError) as exc:
                    raise RuntimeError(f"{SOURCE} malformed eForms XML; cursor not advanced") from exc
                root_name = _local(root.tag)
                if root_name == "ContractNotice":
                    events.extend(_notice_events(
                        root,
                        publication_day=day.isoformat(),
                        filename_notice_id=filename_notice_id,
                        file_version=file_version,
                    ))
                elif root_name == "ContractAwardNotice":
                    events.extend(_award_events(
                        root,
                        publication_day=day.isoformat(),
                        filename_notice_id=filename_notice_id,
                        file_version=file_version,
                        tracked_folders=tracked_folders,
                    ))
                else:
                    # The eForms export includes several notice families. Only
                    # ContractNotice can create a tender opportunity and only
                    # ContractAwardNotice is required for the lifecycle contract
                    # implemented here. Other source-native families are not
                    # converted via text heuristics.
                    continue
            return sorted(events, key=_event_key)

    @staticmethod
    def _apply_events(events, tracked, closed):
        for event in events:
            external_id = str(event.get("external_id") or "").strip()
            if not external_id:
                raise RuntimeError(f"{SOURCE} event missing external identity; cursor not advanced")
            if event.get("closed"):
                current = tracked.pop(external_id, None)
                if current is None:
                    continue
                closed[external_id] = _merge_event(current, event)
                continue
            current = tracked.get(external_id)
            tracked[external_id] = _merge_event(current, event)
            closed.pop(external_id, None)

    @staticmethod
    def _finalize(tracked, closed, *, now):
        observations = []
        survivors = {}
        current = _parse_source_datetime(now) or datetime.now(timezone.utc)

        for external_id, state in closed.items():
            if state.get("was_visible"):
                observations.append(_observation(
                    state,
                    actionable=False,
                    lifecycle_status="awarded_or_completed",
                    lifecycle_reason="publisher ContractAwardNotice closes the tender opportunity",
                    lifecycle_only=True,
                ))

        for external_id, state in tracked.items():
            deadline = _parse_source_datetime(state.get("deadline"))
            if deadline is not None and deadline > current:
                state["was_visible"] = True
                survivors[external_id] = state
                observations.append(_observation(
                    state,
                    actionable=True,
                    lifecycle_status="active",
                    lifecycle_reason="publisher reports Works ContractNotice with future lot submission deadline",
                ))
                continue

            if deadline is None:
                if state.get("was_visible"):
                    observations.append(_observation(
                        state,
                        actionable=False,
                        lifecycle_status="deadline_missing",
                        lifecycle_reason="tracked Works lot no longer has a valid structured submission deadline",
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
                    lifecycle_reason="lot submission deadline has elapsed",
                    lifecycle_only=True,
                ))
        return observations, survivors

    def fetch_incremental(self, *, watermark=None, now=None):
        current = _parse_source_datetime(now) or datetime.now(timezone.utc)
        target = self._target_day(current)
        cursor = GermanDOECursor.decode(watermark) if watermark else None
        tracked = deepcopy(cursor.tracked) if cursor else {}
        closed = deepcopy(cursor.closed) if cursor else {}

        if cursor:
            completed = _parse_day(cursor.completed_through, label="completed_through")
            if completed > target:
                raise RuntimeError(f"{SOURCE} cursor is ahead of latest closed pubDay; cursor not advanced")
            start = completed + timedelta(days=1)
            if self.overlap_days:
                start = start - timedelta(days=self.overlap_days)
        else:
            completed = target - timedelta(days=self.initial_lookback_days)
            start = completed + timedelta(days=1)

        days = []
        day = start
        while day <= target and len(days) < self.max_days_per_sync:
            days.append(day)
            day += timedelta(days=1)

        for pub_day in days:
            data = self._download_day(pub_day)
            events = self._archive_events(pub_day, data, tracked=tracked)
            self._apply_events(events, tracked, closed)
            if pub_day > completed:
                completed = pub_day

        caught_up = completed >= target
        if caught_up:
            observations, tracked = self._finalize(tracked, closed, now=current)
            closed = {}
        else:
            # Do not expose an intermediate historical state while a bounded
            # bootstrap/catch-up still has later publication-day partitions to
            # apply. A later award or correction can materially change truth.
            observations = []

        next_cursor = GermanDOECursor(completed.isoformat(), tracked, closed).encode()
        return observations, next_cursor


def build_germany_doe_connector(*, session=None, **kwargs):
    return GermanDOEOpenDataConnector(session=session, **kwargs)


def fetch_germany_doe_tenders(*, watermark=None, now=None, connector=None):
    client = connector or build_germany_doe_connector()
    return client.fetch_incremental(watermark=watermark, now=now)
