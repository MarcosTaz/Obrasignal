"""Estonia Riigihangete Register (RHR) public eForms bulk connector.

RHR publishes public month-partitioned XML for contract notices and contract
award notices. The current month is mutable and is therefore re-read; previous
months provide overlap. Only publisher-native ``ProcurementTypeCode=works``
records create opportunities. Opportunities are lot-level because CPV and
submission deadlines can differ by lot.

Live validation on 2026-08-24 established ``ContractFolderID`` as stable
procedure identity across republications and awards, while notice ``ID`` is the
publication identity. ``VersionID`` remained ``01`` across republications, so
``IssueDate`` + ``IssueTime`` is the ordering key.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from xml.etree.ElementTree import ParseError, XMLPullParser
from zoneinfo import ZoneInfo

import requests


SOURCE = "EE_RHR"
COUNTRY = "EST"
RHR_BASE = "https://riigihanked.riik.ee/rhr/api/public/v1/opendata"
RHR_ATTRIBUTION = "Riigihangete Register (RHR), Estonia"
RHR_DATASET = "Riigihangete register open data — XML eForms"
RHR_HEADERS = {
    "Accept": "application/xml,text/xml,*/*",
    "User-Agent": "ObraSignal RHR connector/1.0 (+official open-data ingestion)",
}
TALLINN = ZoneInfo("Europe/Tallinn")


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
        parsed = parsed.replace(tzinfo=TALLINN)
    return parsed.astimezone(timezone.utc)


def _utc(value):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _issue_timestamp(root):
    return _parse_issue(_direct_text(root, "IssueDate"), _direct_text(root, "IssueTime"))


def _cpvs(elem):
    out = []
    for child in elem.iter() if elem is not None else ():
        if _local(child.tag) != "ItemClassificationCode":
            continue
        if child.attrib.get("listName") not in (None, "cpv"):
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
    buyer_id = _path_text(party, "PartyIdentification", "ID")
    return _organization_map(root).get(buyer_id, {})


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


def _human_uri(root):
    for child in root.iter():
        if _local(child.tag) not in {"URI", "WebsiteURI", "BuyerProfileURI"}:
            continue
        value = _text(child)
        if "riigihanked.riik.ee/rhr-web/#/procurement/" in value:
            return value
    return ""


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


def _notice_events(root):
    if _local(root.tag) != "ContractNotice":
        return []
    project = _project(root)
    if _direct_text(project, "ProcurementTypeCode").lower() != "works":
        return []

    folder_id = _direct_text(root, "ContractFolderID")
    notice_id = _direct_text(root, "ID")
    issued = _issue_timestamp(root)
    if not folder_id or not notice_id or issued is None:
        raise RuntimeError(
            "EE_RHR Works notice missing ContractFolderID/ID/IssueDate+IssueTime; cursor not advanced"
        )
    lots = _notice_lots(root)
    if not lots:
        raise RuntimeError("EE_RHR Works notice contains no ProcurementProjectLot; cursor not advanced")

    buyer_info = _buyer(root)
    project_title = _direct_text(project, "Name")
    project_description = _direct_text(project, "Description")
    project_cpvs = _cpvs(project)
    place = _project_place(project, buyer_info)
    value, currency = _amount(project)
    process = _first_desc(root, "TenderingProcess")
    procedure_method = _direct_text(process, "ProcedureCode")
    human_uri = _human_uri(root)
    notice_type = _direct_text(root, "NoticeTypeCode")
    issued_utc = _utc(issued)

    events = []
    for lot in lots:
        lot_id = _direct_text(lot, "ID")
        if not lot_id:
            raise RuntimeError("EE_RHR Works lot missing ID; cursor not advanced")
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
            "notice_type": notice_type,
            "event_kind": "notice",
            "closed": False,
            "title": title,
            "description": project_description or title,
            "buyer": str(buyer_info.get("name") or "").strip(),
            "place": place,
            "cpv_codes": cpvs,
            "deadline": _lot_deadline(lot),
            "value": lot_value or value,
            "currency": lot_currency or currency,
            "first_published_at": issued_utc,
            "source_updated_at": issued_utc,
            "url": human_uri,
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


def _award_events(root, tracked_folders=()):
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
        raise RuntimeError(
            "EE_RHR relevant award missing ContractFolderID/ID/IssueDate+IssueTime; cursor not advanced"
        )
    lot_ids = _award_lot_ids(root)
    if not lot_ids:
        raise RuntimeError("EE_RHR relevant award contains no lot identities; cursor not advanced")
    return [{
        "external_id": f"{folder_id}::{lot_id}",
        "procedure_id": folder_id,
        "lot_id": lot_id,
        "notice_id": notice_id,
        "notice_type": _direct_text(root, "NoticeTypeCode"),
        "event_kind": "award",
        "closed": True,
        "source_updated_at": _utc(issued),
        "was_visible": False,
    } for lot_id in lot_ids]


def _event_time(event):
    try:
        parsed = datetime.fromisoformat(str(event.get("source_updated_at") or "").replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _merge_event(current, event):
    if current is None:
        return deepcopy(event)
    if _event_time(event) < _event_time(current):
        return current
    visible = bool(current.get("was_visible")) or bool(event.get("was_visible"))
    if event.get("closed"):
        closed = deepcopy(current)
        closed.update({
            "notice_id": event.get("notice_id") or current.get("notice_id"),
            "notice_type": event.get("notice_type") or current.get("notice_type"),
            "event_kind": "award",
            "closed": True,
            "source_updated_at": event.get("source_updated_at") or current.get("source_updated_at"),
            "was_visible": visible,
        })
        return closed
    updated = deepcopy(event)
    updated["was_visible"] = visible
    first = str(current.get("first_published_at") or "").strip()
    if first and (not updated.get("first_published_at") or first < str(updated.get("first_published_at"))):
        updated["first_published_at"] = first
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
        "publication_date": str(state.get("first_published_at") or "")[:10],
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
        "rhr_contract_folder_id": str(state.get("procedure_id") or ""),
        "lot_id": str(state.get("lot_id") or ""),
        "lot_count": int(state.get("lot_count") or 1),
        "attribution": RHR_ATTRIBUTION,
        "source_dataset": RHR_DATASET,
        "source_api_url": RHR_BASE,
        "source_modified": True,
        "is_actionable": bool(actionable),
        "lifecycle_status": lifecycle_status,
        "lifecycle_reason": lifecycle_reason,
    }
    if lifecycle_only or not actionable:
        row["_lifecycle_only"] = True
    return row


@dataclass
class EERHRCursor:
    observed_through: str
    tracked: dict
    periods: tuple[str, ...] = ()
    catchup_next: str = ""

    def encode(self):
        return json.dumps({
            "observed_through": self.observed_through,
            "tracked": self.tracked,
            "periods": list(self.periods),
            "catchup_next": self.catchup_next,
        }, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    @classmethod
    def decode(cls, value):
        if not value:
            return None
        try:
            payload = json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("invalid EE_RHR cursor JSON") from exc
        observed = str(payload.get("observed_through") or "").strip()
        tracked = payload.get("tracked") or {}
        periods = payload.get("periods") or []
        catchup_next = str(payload.get("catchup_next") or "").strip()
        if not observed or not isinstance(tracked, dict) or not isinstance(periods, list):
            raise RuntimeError("invalid EE_RHR cursor state")
        try:
            datetime.fromisoformat(observed.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RuntimeError("invalid EE_RHR cursor observed_through") from exc
        if catchup_next:
            _parse_month(catchup_next)
        return cls(observed, tracked, tuple(str(period) for period in periods if period), catchup_next)


def _shift_month(year, month, offset):
    index = year * 12 + (month - 1) + int(offset)
    return index // 12, index % 12 + 1


def _periods(now, count):
    local_now = now.astimezone(TALLINN)
    total = max(1, int(count))
    return [
        _shift_month(local_now.year, local_now.month, offset)
        for offset in range(-(total - 1), 1)
    ]


def _month_text(period):
    return f"{period[0]:04d}-{period[1]:02d}"


def _parse_month(value):
    text = str(value or "").strip()
    try:
        year_text, month_text = text.split("-", 1)
        year, month = int(year_text), int(month_text)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("invalid EE_RHR cursor catchup_next") from exc
    if year < 2000 or month < 1 or month > 12:
        raise RuntimeError("invalid EE_RHR cursor catchup_next")
    return year, month


def _month_range(start, end):
    start_index = start[0] * 12 + start[1] - 1
    end_index = end[0] * 12 + end[1] - 1
    if start_index > end_index:
        return []
    return [(index // 12, index % 12 + 1) for index in range(start_index, end_index + 1)]


class EstoniaRHRConnector:
    def __init__(
        self,
        *,
        session=None,
        initial_months=3,
        overlap_months=1,
        max_months_per_sync=4,
        max_resource_bytes=80 * 1024 * 1024,
        timeout=120,
    ):
        self.session = session or requests.Session()
        self.initial_months = max(1, int(initial_months))
        self.overlap_months = max(0, int(overlap_months))
        self.max_months_per_sync = max(self.initial_months, int(max_months_per_sync), 1)
        self.max_resource_bytes = max(1024, int(max_resource_bytes))
        self.timeout = max(1, int(timeout))

    def _url(self, surface, year, month):
        return f"{RHR_BASE}/{surface}/{year}/month/{month}/xml"

    def _roots(self, surface, year, month):
        expected = "ContractNotice" if surface == "notice" else "ContractAwardNotice"
        response = self.session.get(
            self._url(surface, year, month),
            headers=RHR_HEADERS,
            timeout=self.timeout,
            stream=True,
            allow_redirects=True,
        )
        response.raise_for_status()
        try:
            length = int(response.headers.get("content-length") or 0)
        except (TypeError, ValueError):
            length = 0
        if length and length > self.max_resource_bytes:
            response.close()
            raise RuntimeError(
                f"EE_RHR {year}-{month:02d} {surface} resource exceeds max_resource_bytes="
                f"{self.max_resource_bytes}; cursor not advanced"
            )

        parser = XMLPullParser(events=("start", "end"))
        received = 0
        wrapper = None
        try:
            for chunk in response.iter_content(chunk_size=131072):
                if not chunk:
                    continue
                received += len(chunk)
                if received > self.max_resource_bytes:
                    raise RuntimeError(
                        f"EE_RHR {year}-{month:02d} {surface} stream exceeded max_resource_bytes="
                        f"{self.max_resource_bytes}; cursor not advanced"
                    )
                try:
                    parser.feed(chunk)
                    for event, elem in parser.read_events():
                        local = _local(elem.tag)
                        if event == "start" and wrapper is None:
                            wrapper = local
                            if wrapper != "OPEN-DATA":
                                raise RuntimeError(
                                    f"EE_RHR {surface} XML has unexpected root {wrapper}; cursor not advanced"
                                )
                        elif event == "end" and local == expected:
                            yield elem
                            elem.clear()
                except RuntimeError:
                    raise
                except (ParseError, ValueError) as exc:
                    raise RuntimeError(
                        f"EE_RHR {surface} XML parse failure; cursor not advanced"
                    ) from exc
            try:
                parser.close()
            except (ParseError, ValueError) as exc:
                raise RuntimeError(
                    f"EE_RHR {surface} XML parse failure; cursor not advanced"
                ) from exc
            if not received or wrapper != "OPEN-DATA":
                raise RuntimeError(
                    f"EE_RHR {surface} XML missing OPEN-DATA wrapper; cursor not advanced"
                )
        finally:
            response.close()

    def _apply_period(self, states, year, month):
        seen_notices = set()
        for root in self._roots("notice", year, month):
            for event in _notice_events(root):
                key = (event.get("notice_id"), event.get("lot_id"))
                if key in seen_notices:
                    continue
                seen_notices.add(key)
                external_id = event["external_id"]
                states[external_id] = _merge_event(states.get(external_id), event)

        folders = {
            str(state.get("procedure_id") or "")
            for state in states.values()
            if isinstance(state, dict) and state.get("procedure_id")
        }
        seen_awards = set()
        for root in self._roots("notice_award", year, month):
            for event in _award_events(root, tracked_folders=folders):
                key = (event.get("notice_id"), event.get("lot_id"))
                if key in seen_awards:
                    continue
                seen_awards.add(key)
                external_id = event["external_id"]
                if external_id not in states:
                    continue
                states[external_id] = _merge_event(states.get(external_id), event)

    def _finalize(self, states, current):
        observations = []
        next_tracked = {}
        for external_id in sorted(states):
            state = states[external_id]
            was_visible = bool(state.get("was_visible"))
            if state.get("closed"):
                if was_visible:
                    observations.append(_observation(
                        state,
                        actionable=False,
                        lifecycle_status="result_published",
                        lifecycle_reason="RHR ContractAwardNotice published for this procurement lot",
                        lifecycle_only=True,
                    ))
                continue

            deadline_text = str(state.get("deadline") or "").strip()
            try:
                deadline = datetime.fromisoformat(deadline_text.replace("Z", "+00:00")) if deadline_text else None
            except ValueError:
                deadline = None
            if deadline is not None and deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)

            if deadline is not None and deadline.astimezone(timezone.utc) > current:
                observations.append(_observation(
                    state,
                    actionable=True,
                    lifecycle_status="active",
                    lifecycle_reason="RHR publishes a Works lot with a future submission deadline",
                ))
                state["was_visible"] = True
                next_tracked[external_id] = state
            elif was_visible:
                observations.append(_observation(
                    state,
                    actionable=False,
                    lifecycle_status="deadline_missing" if deadline is None else "deadline_elapsed",
                    lifecycle_reason=(
                        "RHR Works lot no longer has a valid submission deadline"
                        if deadline is None else "RHR submission deadline has elapsed"
                    ),
                    lifecycle_only=True,
                ))
        return observations, next_tracked

    def fetch_incremental(self, *, watermark=None, now=None):
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        current = current.astimezone(timezone.utc)
        local_current = current.astimezone(TALLINN)
        current_period = (local_current.year, local_current.month)

        cursor = EERHRCursor.decode(watermark) if watermark else None
        states = deepcopy(cursor.tracked) if cursor else {}
        if cursor and not cursor.catchup_next:
            # A normal completed cursor contains only lots that were already
            # visible. Older cursor versions did not persist this flag.
            for state in states.values():
                if isinstance(state, dict):
                    state["was_visible"] = True

        if cursor and cursor.catchup_next:
            start_period = _parse_month(cursor.catchup_next)
        elif cursor:
            observed = datetime.fromisoformat(cursor.observed_through.replace("Z", "+00:00"))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            local_observed = observed.astimezone(TALLINN)
            start_period = _shift_month(
                local_observed.year,
                local_observed.month,
                -self.overlap_months,
            )
        else:
            initial = _periods(current, self.initial_months)
            start_period = initial[0]

        pending_periods = _month_range(start_period, current_period)
        if not pending_periods:
            pending_periods = [current_period]
        batch = pending_periods[:self.max_months_per_sync]
        for year, month in batch:
            self._apply_period(states, year, month)

        caught_up = batch[-1] == current_period
        period_labels = tuple(_month_text(period) for period in batch)
        if not caught_up:
            next_period = _shift_month(batch[-1][0], batch[-1][1], 1)
            # Preserve the last fully published timestamp while carrying the
            # working state forward. No intermediate opportunity/tombstone is
            # emitted because a later skipped month may change the truth.
            observed_through = cursor.observed_through if cursor else _utc(current)
            next_cursor = EERHRCursor(
                observed_through=observed_through,
                tracked=states,
                periods=period_labels,
                catchup_next=_month_text(next_period),
            ).encode()
            return [], next_cursor

        observations, next_tracked = self._finalize(states, current)
        next_cursor = EERHRCursor(
            observed_through=_utc(current),
            tracked=next_tracked,
            periods=period_labels,
            catchup_next="",
        ).encode()
        return observations, next_cursor


def build_estonia_rhr_connector(*, session=None, **kwargs):
    return EstoniaRHRConnector(session=session, **kwargs)


def fetch_estonia_rhr_tenders(*, watermark=None, now=None, connector=None):
    client = connector or build_estonia_rhr_connector()
    return client.fetch_incremental(watermark=watermark, now=now)
