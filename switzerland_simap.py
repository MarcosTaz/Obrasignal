"""Swiss SIMAP public construction-procurement connector.

Discovery uses the official public project-search API with structured
``projectSubTypes=construction`` and ``newestPubTypes=tender`` filters. The
opaque ``lastItem`` value is used only while paging one search; the durable
cursor is a date watermark plus previously live lot/project targets so lifecycle
monitoring outlives the recent discovery window.

SIMAP permits commercial reuse/redistribution, but publication data may only be
communicated to third parties from 08:00 on the publication date. The
normalizer enforces that source-local legal release gate in addition to a
future offer deadline.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import json
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests


SOURCE = "CH_SIMAP"
COUNTRY = "CHE"
SIMAP_BASE = "https://www.simap.ch/api"
SIMAP_SEARCH = f"{SIMAP_BASE}/publications/v2/project/project-search"
SIMAP_HEADER = f"{SIMAP_BASE}/publications/v2/project/{{project_id}}/project-header"
SIMAP_DETAIL = (
    f"{SIMAP_BASE}/publications/v1/project/{{project_id}}/"
    "publication-details/{publication_id}"
)
SIMAP_HUMAN = "https://www.simap.ch/en/project-detail/{project_id}"
SIMAP_TERMS = "https://www.simap.ch/en/about/legal"
SIMAP_ATTRIBUTION = "Association simap.ch"
SIMAP_OFFICIAL_DISCLAIMER = (
    "Dies ist keine amtliche Veröffentlichung. Massgebend sind die auf der "
    "Plattform www.simap.ch veröffentlichten Daten."
)
SIMAP_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal SIMAP connector/1.0 (+official public API client)",
}
ZURICH = ZoneInfo("Europe/Zurich")


def _text(value):
    return "" if value is None else str(value).strip()


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _localized(value):
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""
    for language in ("en", "de", "fr", "it"):
        text = _text(value.get(language))
        if text:
            return text
    for candidate in value.values():
        text = _text(candidate)
        if text:
            return text
    return ""


def _parse_dt(value, *, default_tz=ZURICH):
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
        parsed = parsed.replace(tzinfo=default_tz)
    return parsed


def _utc_now(value=None):
    parsed = _parse_dt(value, default_tz=timezone.utc)
    return (parsed or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _source_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.astimezone(ZURICH).date() if value.tzinfo else value.date()
    if value:
        try:
            return date.fromisoformat(_text(value)[:10])
        except ValueError:
            return None
    return None


def _legal_available_at(publication_date):
    day = _source_date(publication_date)
    if day is None:
        return None
    return datetime.combine(day, time(hour=8), tzinfo=ZURICH)


def _target(project_id, lot_id=None):
    project_id = _text(project_id)
    lot_id = _text(lot_id)
    return f"{project_id}:lot:{lot_id}" if lot_id else project_id


def _project_from_target(target):
    value = _text(target)
    return value.partition(":lot:")[0]


def _values_from_code_field(value):
    """Return conservative classification codes without guessing conversions."""
    found = []

    def visit(node):
        if node is None:
            return
        if isinstance(node, (str, int)):
            text = _text(node)
            if text and text not in found:
                found.append(text)
            return
        if isinstance(node, list):
            for child in node:
                visit(child)
            return
        if isinstance(node, dict):
            used = False
            for key in ("code", "id", "key", "value", "number"):
                if key in node and isinstance(node.get(key), (str, int)):
                    visit(node.get(key))
                    used = True
            if not used:
                for key, child in node.items():
                    lowered = str(key).lower()
                    if "description" in lowered or "label" in lowered or "name" in lowered:
                        continue
                    if "code" in lowered or lowered in {"id", "key", "value", "number"}:
                        visit(child)

    visit(value)
    return found


def _classification_codes(container, names):
    container = _dict(container)
    codes = []
    for name in names:
        for code in _values_from_code_field(container.get(name)):
            if code not in codes:
                codes.append(code)
    return codes


def _address_text(address):
    address = _dict(address)
    pieces = []
    city = _localized(address.get("city"))
    for value in (
        city,
        _text(address.get("postalCode")),
        _text(address.get("cantonId")),
        _text(address.get("countryId")),
    ):
        if value and value not in pieces:
            pieces.append(value)
    return " | ".join(pieces)


def _nested_text(container, *paths):
    for path in paths:
        node = container
        ok = True
        for key in path:
            if not isinstance(node, dict) or key not in node:
                ok = False
                break
            node = node[key]
        if ok:
            value = _localized(node) if isinstance(node, dict) else _text(node)
            if value:
                return value
    return ""


def _publication_dates(publication):
    return _dict(publication.get("dates"))


def _actionability(publication, *, now=None):
    publication = _dict(publication)
    pub_type = _text(publication.get("pubType") or _publication_dates(publication).get("pubType")).lower()
    publication_date = _source_date(_publication_dates(publication).get("publicationDate"))
    current = _utc_now(now)

    if pub_type != "tender":
        if pub_type == "revocation":
            return False, "revoked", "latest SIMAP publication revokes the procurement"
        if pub_type == "abandonment":
            return False, "abandoned", "latest SIMAP publication abandons the procurement"
        return False, pub_type or "inactive", f"latest SIMAP publication type is {pub_type or 'missing'}"

    legal_at = _legal_available_at(publication_date)
    if legal_at is None:
        return False, "publication_date_missing", "tender publication has no valid publication date"
    if current < legal_at.astimezone(timezone.utc):
        return False, "legal_release_pending", "SIMAP reuse terms prohibit third-party communication before 08:00 on publication date"

    deadline_raw = (
        _publication_dates(publication).get("offerDeadline")
        or _publication_dates(publication).get("offerSubmissionDeadline")
    )
    if isinstance(deadline_raw, dict):
        deadline_raw = deadline_raw.get("dateTime") or deadline_raw.get("date") or deadline_raw.get("value")
    deadline = _parse_dt(deadline_raw)
    if deadline is None:
        return False, "deadline_missing", "current SIMAP tender has no valid offer deadline"
    if deadline.astimezone(timezone.utc) <= current:
        return False, "deadline_expired", "SIMAP offer deadline has passed"
    return True, "active", "current SIMAP construction tender has a future offer deadline and is legally releasable"


def _detail_lot(detail, lot_id):
    for row in _list(_dict(detail).get("lots")):
        if isinstance(row, dict) and _text(row.get("id")) == _text(lot_id):
            return row
    return {}


def _primary_taxonomy(detail_scope, procurement):
    cpv = _classification_codes(detail_scope, ("cpvCode", "cpvCodes", "additionalCpvCodes"))
    if not cpv:
        cpv = _classification_codes(procurement, ("cpvCode", "cpvCodes", "additionalCpvCodes"))
    cpc = _classification_codes(detail_scope, ("cpcCode", "cpcCodes"))
    if not cpc:
        cpc = _classification_codes(procurement, ("cpcCode", "cpcCodes"))
    bkp = _classification_codes(detail_scope, ("bkpCode", "bkpCodes"))
    if not bkp:
        bkp = _classification_codes(procurement, ("bkpCode", "bkpCodes"))
    ebkph = _classification_codes(detail_scope, ("ebkphCode", "ebkphCodes"))
    if not ebkph:
        ebkph = _classification_codes(procurement, ("ebkphCode", "ebkphCodes"))
    ebkpt = _classification_codes(detail_scope, ("ebkptCode", "ebkptCodes"))
    if not ebkpt:
        ebkpt = _classification_codes(procurement, ("ebkptCode", "ebkptCodes"))
    npk = _classification_codes(detail_scope, ("npkCode", "npkCodes"))
    if not npk:
        npk = _classification_codes(procurement, ("npkCode", "npkCodes"))
    oag = _classification_codes(detail_scope, ("oagCode", "oagCodes"))
    if not oag:
        oag = _classification_codes(procurement, ("oagCode", "oagCodes"))

    if cpv:
        taxonomy, category = "CPV", cpv[0]
    elif cpc:
        taxonomy, category = "CPC", cpc[0]
    elif bkp:
        taxonomy, category = "BKP", bkp[0]
    elif ebkph:
        taxonomy, category = "eBKP-H", ebkph[0]
    elif ebkpt:
        taxonomy, category = "eBKP-T", ebkpt[0]
    elif npk:
        taxonomy, category = "NPK", npk[0]
    elif oag:
        taxonomy, category = "OAG", oag[0]
    else:
        taxonomy, category = "", ""

    return {
        "taxonomy": taxonomy,
        "category_code": category,
        "cpv_codes": cpv,
        "cpc_codes": cpc,
        "bkp_codes": bkp,
        "ebkph_codes": ebkph,
        "ebkpt_codes": ebkpt,
        "npk_codes": npk,
        "oag_codes": oag,
    }


def normalize_simap_target(project_header, publication, *, detail=None, discovery=None, lot=None, now=None):
    """Normalize one current project/lot target from publisher-authoritative state."""
    header = _dict(project_header)
    publication = _dict(publication)
    discovery = _dict(discovery)
    lot = _dict(lot)
    project_id = _text(header.get("id") or discovery.get("id"))
    lot_id = _text(lot.get("id") or lot.get("lotId"))
    if not project_id:
        raise RuntimeError("SIMAP project header is missing id")

    project_subtype = _text(lot.get("projectSubType") or publication.get("projectSubType") or header.get("projectSubType")).lower()
    if project_subtype != "construction":
        return None

    external_id = _target(project_id, lot_id)
    actionable, lifecycle_status, lifecycle_reason = _actionability(publication, now=now)
    dates = _publication_dates(publication)
    publication_date = _text(dates.get("publicationDate") or discovery.get("publicationDate"))
    legal_at = _legal_available_at(publication_date)

    deadline_raw = dates.get("offerDeadline") or dates.get("offerSubmissionDeadline")
    if isinstance(deadline_raw, dict):
        deadline_raw = deadline_raw.get("dateTime") or deadline_raw.get("date") or deadline_raw.get("value")
    deadline = _text(deadline_raw)

    detail = _dict(detail)
    procurement = _dict(detail.get("procurement"))
    detail_scope = _detail_lot(detail, lot_id) if lot_id else procurement
    classifications = _primary_taxonomy(detail_scope, procurement)
    primary_cpv = classifications["cpv_codes"][0] if classifications["cpv_codes"] else ""

    title = (
        _localized(lot.get("title"))
        or _localized(lot.get("lotTitle"))
        or _localized(publication.get("title"))
        or _localized(discovery.get("title"))
        or f"SIMAP project {_text(header.get('projectNumber')) or project_id}"
    )
    project_title = _localized(publication.get("title")) or _localized(discovery.get("title"))
    if lot_id and project_title and project_title != title:
        lot_number = _text(lot.get("lotNumber"))
        label = f"Lot {lot_number}" if lot_number else "Lot"
        title = f"{project_title} — {label}: {title}"

    project_info = _dict(detail.get("project-info"))
    buyer = (
        _localized(discovery.get("procOfficeName"))
        or _nested_text(project_info, ("procOfficeName",), ("procurementOfficeName",), ("procOffice", "name"))
    )
    order_address = (
        _dict(lot.get("orderAddress"))
        or _dict(detail_scope.get("orderAddress"))
        or _dict(procurement.get("orderAddress"))
        or _dict(discovery.get("orderAddress"))
    )
    place = _address_text(order_address)

    pub_type = _text(publication.get("pubType") or dates.get("pubType")).lower()
    publication_id = _text(publication.get("id") or discovery.get("publicationId"))
    publication_number = _text(publication.get("publicationNumber") or discovery.get("publicationNumber"))
    process_type = _text(publication.get("processType") or header.get("processType") or discovery.get("processType"))
    construction_type = _text(detail_scope.get("constructionType") or procurement.get("constructionType"))
    corrected = bool(publication.get("corrected"))
    correction = _dict(detail.get("correction"))
    correction_keys = [str(row) for row in _list(correction.get("correctionDiffKeys")) if _text(row)]

    source_updated = legal_at.isoformat() if legal_at is not None else (publication_date or None)
    item = {
        "source": SOURCE,
        "external_id": external_id,
        "title": title,
        "description": _nested_text(
            detail_scope,
            ("description",),
            ("orderDescription",),
            ("shortDescription",),
        ) or _nested_text(procurement, ("description",), ("orderDescription",), ("shortDescription",)),
        "buyer": buyer,
        "country": COUNTRY,
        "cpv": primary_cpv,
        "taxonomy": classifications["taxonomy"],
        "category_code": classifications["category_code"],
        **classifications,
        "value": "",
        "currency": "",
        "deadline": deadline,
        "publication_date": publication_date,
        "published_at": source_updated,
        "source_updated_at": source_updated,
        "url": SIMAP_HUMAN.format(project_id=quote(project_id, safe="")),
        "market": "GLOBAL",
        "place": place,
        "source_status": pub_type,
        "source_phase": process_type,
        "signal_type": "TENDER",
        "procurement_method": process_type,
        "contract_type": construction_type or "construction",
        "source_reference": publication_id or publication_number,
        "project_id": project_id,
        "project_number": _text(header.get("projectNumber") or discovery.get("projectNumber")),
        "lot_id": lot_id,
        "lot_number": _text(lot.get("lotNumber")),
        "publication_id": publication_id,
        "publication_number": publication_number,
        "corrected": corrected,
        "correction_diff_keys": correction_keys,
        "source_api_url": (
            SIMAP_DETAIL.format(
                project_id=quote(project_id, safe=""),
                publication_id=quote(publication_id, safe=""),
            )
            if publication_id else SIMAP_HEADER.format(project_id=quote(project_id, safe=""))
        ),
        "source_terms_url": SIMAP_TERMS,
        "attribution": SIMAP_ATTRIBUTION,
        "official_disclaimer": SIMAP_OFFICIAL_DISCLAIMER,
        "reuse_available_from": legal_at.isoformat() if legal_at else None,
        "source_dataset": "simap.ch public procurement publications",
        "source_modified": True,
        "is_actionable": actionable,
        "lifecycle_status": lifecycle_status,
        "lifecycle_reason": lifecycle_reason,
    }
    if not actionable:
        item["_lifecycle_only"] = True
    return item


@dataclass(frozen=True)
class SIMAPCursor:
    observed_through: str
    tracked_targets: tuple = ()

    def encode(self):
        return json.dumps(
            {
                "observed_through": self.observed_through,
                "tracked_targets": sorted(set(self.tracked_targets)),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def decode(cls, watermark):
        if not watermark:
            return None
        try:
            payload = json.loads(str(watermark))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("invalid SIMAP cursor; cursor not advanced") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("invalid SIMAP cursor; cursor not advanced")
        observed = _text(payload.get("observed_through"))
        if not _source_date(observed):
            raise RuntimeError("invalid SIMAP cursor observed_through; cursor not advanced")
        tracked = payload.get("tracked_targets", ())
        if tracked is None:
            tracked = ()
        if not isinstance(tracked, (list, tuple)):
            raise RuntimeError("invalid SIMAP cursor tracked_targets; cursor not advanced")
        values = tuple(sorted({_text(row) for row in tracked if _text(row)}))
        return cls(observed_through=observed, tracked_targets=values)


class SIMAPConnector:
    def __init__(
        self,
        *,
        session=None,
        initial_lookback_days=14,
        overlap_days=2,
        max_pages_per_sync=50,
        max_project_hydrations_per_sync=500,
        max_detail_hydrations_per_sync=1000,
        timeout=45,
    ):
        self.session = session or requests.Session()
        self.initial_lookback_days = max(1, int(initial_lookback_days))
        self.overlap_days = max(1, int(overlap_days))
        self.max_pages_per_sync = max(1, int(max_pages_per_sync))
        self.max_project_hydrations_per_sync = max(1, int(max_project_hydrations_per_sync))
        self.max_detail_hydrations_per_sync = max(1, int(max_detail_hydrations_per_sync))
        self.timeout = int(timeout)

    def _get(self, url, *, params=None):
        response = self.session.get(url, params=params or {}, headers=SIMAP_HEADERS, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError(f"SIMAP endpoint returned non-object JSON from {url}; cursor not advanced")
        return payload

    def _window(self, cursor, today):
        if cursor is None:
            return today - timedelta(days=self.initial_lookback_days), today
        observed = _source_date(cursor.observed_through)
        if observed is None or observed > today:
            raise RuntimeError("SIMAP cursor observed_through is invalid/future; cursor not advanced")
        return observed - timedelta(days=self.overlap_days), today

    def _search(self, start, end):
        base_params = [
            ("newestPublicationFrom", start.isoformat()),
            ("newestPublicationUntil", end.isoformat()),
            ("projectSubTypes", "construction"),
            ("newestPubTypes", "tender"),
        ]
        rows = {}
        token = None
        for page_number in range(1, self.max_pages_per_sync + 1):
            params = list(base_params)
            if token:
                params.append(("lastItem", token))
            payload = self._get(SIMAP_SEARCH, params=params)
            projects = payload.get("projects")
            pagination = payload.get("pagination")
            if not isinstance(projects, list) or not isinstance(pagination, dict):
                raise RuntimeError("SIMAP search response missing projects/pagination; cursor not advanced")
            for row in projects:
                if not isinstance(row, dict):
                    raise RuntimeError("SIMAP search returned malformed project row; cursor not advanced")
                project_id = _text(row.get("id"))
                if not project_id:
                    raise RuntimeError("SIMAP search returned project without id; cursor not advanced")
                if _text(row.get("projectSubType")).lower() != "construction":
                    continue
                rows[project_id] = row

            next_token = _text(pagination.get("lastItem"))
            if not next_token:
                return rows
            if next_token == token:
                raise RuntimeError("SIMAP search repeated lastItem token; cursor not advanced")
            token = next_token

        raise RuntimeError(
            f"SIMAP search exceeded max_pages_per_sync={self.max_pages_per_sync}; cursor not advanced"
        )

    def _header(self, project_id):
        payload = self._get(SIMAP_HEADER.format(project_id=quote(project_id, safe="")))
        if _text(payload.get("id")) != project_id:
            raise RuntimeError(f"SIMAP project header identity mismatch for {project_id}; cursor not advanced")
        return payload

    def _detail(self, project_id, publication_id):
        return self._get(
            SIMAP_DETAIL.format(
                project_id=quote(project_id, safe=""),
                publication_id=quote(publication_id, safe=""),
            )
        )

    @staticmethod
    def _header_targets(header):
        lots = [row for row in _list(header.get("lots")) if isinstance(row, dict)]
        lots_type = _text(header.get("lotsType")).lower()
        if lots or lots_type == "with":
            targets = []
            for lot in lots:
                if _text(lot.get("projectSubType")).lower() != "construction":
                    continue
                lot_id = _text(lot.get("id"))
                if not lot_id:
                    raise RuntimeError("SIMAP construction lot is missing id; cursor not advanced")
                targets.append((lot, _dict(lot.get("latestPublication"))))
            return targets

        if _text(header.get("projectSubType")).lower() != "construction":
            return []
        return [({}, _dict(header.get("latestPublication")))]

    def fetch_incremental(self, *, watermark=None, now=None):
        current = _utc_now(now)
        today = current.astimezone(ZURICH).date()
        cursor = SIMAPCursor.decode(watermark)
        start, end = self._window(cursor, today)
        discovery = self._search(start, end)
        previously_tracked = set(cursor.tracked_targets if cursor else ())
        projects = set(discovery) | {_project_from_target(row) for row in previously_tracked}
        projects.discard("")

        if len(projects) > self.max_project_hydrations_per_sync:
            raise RuntimeError(
                f"SIMAP sync requires {len(projects)} project hydrations, above "
                f"max_project_hydrations_per_sync={self.max_project_hydrations_per_sync}; cursor not advanced"
            )

        headers = {}
        target_specs = []
        for project_id in sorted(projects):
            header = self._header(project_id)
            headers[project_id] = header
            for lot, publication in self._header_targets(header):
                target_specs.append((project_id, lot, publication))

        needed_details = {
            (_text(publication.get("id")), project_id)
            for project_id, _lot, publication in target_specs
            if _text(publication.get("pubType")).lower() == "tender"
            and _text(publication.get("id"))
        }
        if len(needed_details) > self.max_detail_hydrations_per_sync:
            raise RuntimeError(
                f"SIMAP sync requires {len(needed_details)} publication hydrations, above "
                f"max_detail_hydrations_per_sync={self.max_detail_hydrations_per_sync}; cursor not advanced"
            )

        detail_cache = {}
        for publication_id, project_id in sorted(needed_details):
            detail_cache[(project_id, publication_id)] = self._detail(project_id, publication_id)

        observations = []
        current_targets = set()
        next_tracked = set()
        for project_id, lot, publication in target_specs:
            publication_id = _text(publication.get("id"))
            detail = detail_cache.get((project_id, publication_id))
            item = normalize_simap_target(
                headers[project_id],
                publication,
                detail=detail,
                discovery=discovery.get(project_id),
                lot=lot,
                now=current,
            )
            if item is None:
                continue
            current_targets.add(item["external_id"])
            observations.append(item)
            if item.get("is_actionable") or item.get("lifecycle_status") in {
                "legal_release_pending",
                "deadline_missing",
            }:
                next_tracked.add(item["external_id"])

        for missing_target in sorted(previously_tracked - current_targets):
            project_id = _project_from_target(missing_target)
            observations.append(
                {
                    "source": SOURCE,
                    "external_id": missing_target,
                    "country": COUNTRY,
                    "source_reference": project_id,
                    "source_status": "missing_from_current_header",
                    "signal_type": "TENDER",
                    "is_actionable": False,
                    "lifecycle_status": "inactive",
                    "lifecycle_reason": "previously tracked SIMAP target is absent from the current project header",
                    "_lifecycle_only": True,
                }
            )

        next_cursor = SIMAPCursor(
            observed_through=today.isoformat(),
            tracked_targets=tuple(sorted(next_tracked)),
        ).encode()
        return observations, next_cursor


def build_simap_connector(*, session=None, **kwargs):
    return SIMAPConnector(session=session, **kwargs)


def fetch_simap_tenders(*, watermark=None, now=None, connector=None):
    client = connector or build_simap_connector()
    return client.fetch_incremental(watermark=watermark, now=now)
