"""Austria distributed procurement Kerndaten/eForms connector.

Austria publishes procurement core data through datasets registered on the
official data.gv.at catalogue. Each dataset exposes one or more Kerndatenquelle
(KDQ) XML indexes; KDQ items carry a publisher-local publication id, lastmod and
a URL to the actual notice payload.

The connector is intentionally conservative:
- only publisher-native ``TYPE_CONTRACT CTYPE=WORKS`` legacy notices qualify;
- only the live-validated ``KD_8_1_Z2`` legacy family is emitted as TENDER;
- a future structured submission deadline is required for actionability;
- ``KD_8_1_Z1`` prior-information/market-exploration notices are not promoted;
- duplicate publisher aliases are folded into one commercial opportunity while
  all publication aliases remain preserved in metadata;
- a correction to an already-known legacy alias keeps the same canonical
  opportunity identity even when anonymous semantic fields change;
- future Austrian eForms payloads are accepted only when they are standard UBL
  ``ContractNotice`` documents with ``ProcurementTypeCode=works`` and explicit
  lot-level deadlines. Unknown roots fail closed and are never guessed.

The eForms parser is preparatory until Austria's announced 2026-10-01 format
transition can be revalidated live. The current production contract remains the
live-validated catalogue -> KDQ -> legacy notice path.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from xml.etree.ElementTree import XMLPullParser, fromstring
from zoneinfo import ZoneInfo

import requests


SOURCE = "AT_KERNDATEN"
COUNTRY = "AUT"
CATALOG = "https://www.data.gv.at"
CATALOG_SEARCH = f"{CATALOG}/api/hub/search/search"
CATALOG_DATASET = f"{CATALOG}/api/hub/repo/datasets"
CATALOG_URL = "https://www.data.gv.at/"
ATTRIBUTION = "Österreichische Vergabekerndaten via data.gv.at"
VIENNA = ZoneInfo("Europe/Vienna")
HEADERS = {
    "Accept": "application/json,application/ld+json;q=0.9,application/xml;q=0.8,text/xml;q=0.8,*/*;q=0.5",
    "User-Agent": "ObraSignal Austria Kerndaten connector/1.0 (+official open-data ingestion)",
}
LEGACY_ACTIONABLE_ROOTS = {"KD_8_1_Z2"}
EFORMS_NOTICE_ROOT = "ContractNotice"
EFORMS_NON_ACTIONABLE_ROOTS = {"ContractAwardNotice", "PriorInformationNotice"}


def _local(tag):
    return str(tag).rsplit("}", 1)[-1]


def _text(elem):
    if elem is None:
        return ""
    return " ".join(" ".join(elem.itertext()).split())


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


def _parse_source_datetime(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=VIENNA)
    return parsed.astimezone(timezone.utc)


def _parse_eforms_datetime(date_value, time_value):
    date_text = str(date_value or "").strip()
    time_text = str(time_value or "").strip()
    if not date_text or not time_text:
        return None
    date_core = date_text[:10]
    if len(date_core) != 10:
        return None
    try:
        parsed = datetime.fromisoformat(f"{date_core}T{time_text}".replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=VIENNA)
    return parsed.astimezone(timezone.utc)


def _utc(value):
    if value is None:
        return ""
    if isinstance(value, str):
        value = _parse_source_datetime(value)
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _first_paragraph(elem):
    if elem is None:
        return ""
    paragraphs = [_text(child) for child in elem.iter() if _local(child.tag) == "P" and _text(child)]
    return paragraphs[0] if paragraphs else _text(elem)


def _all_code_attributes(elem, tag_name, attr="CODE"):
    out = []
    if elem is None:
        return out
    for child in elem.iter():
        if _local(child.tag) != tag_name:
            continue
        value = str(child.attrib.get(attr) or "").strip()
        if value and value not in out:
            out.append(value)
    return out


def _procedure_code(root):
    procedure = _direct(root, "PROCEDURE")
    if procedure is None:
        return ""
    for child in list(procedure):
        name = _local(child.tag)
        if name.startswith("PT_"):
            return name
    return ""


def _semantic_key(
    dataset_id,
    *,
    buyer_id,
    buyer,
    reference,
    title,
    description,
    cpvs,
    nuts,
    first_publication,
    procedure,
):
    dataset_id = str(dataset_id or "").strip()
    reference = str(reference or "").strip()
    buyer_id = str(buyer_id or "").strip()
    buyer = str(buyer or "").strip()
    if reference:
        authority = buyer_id or buyer
        return f"{dataset_id}:ref:{_sha(authority + '|' + reference)[:28]}"
    basis = "|".join(
        [
            dataset_id,
            buyer,
            str(title or "").strip(),
            str(description or "").strip(),
            ",".join(sorted(str(code) for code in cpvs if str(code))),
            ",".join(sorted(str(code) for code in nuts if str(code))),
            str(first_publication or "").strip(),
            str(procedure or "").strip(),
        ]
    )
    return f"{dataset_id}:anon:{_sha(basis)[:28]}"


def _legacy_state(root, *, dataset_id, item_id, item_lastmod, notice_url):
    root_name = _local(root.tag)
    if root_name not in LEGACY_ACTIONABLE_ROOTS:
        return None

    object_contract = _direct(root, "OBJECT_CONTRACT")
    if object_contract is None:
        raise RuntimeError(f"{SOURCE} {root_name} missing OBJECT_CONTRACT; cursor not advanced")
    contract_type = _direct(object_contract, "TYPE_CONTRACT")
    if contract_type is None or str(contract_type.attrib.get("CTYPE") or "").strip().upper() != "WORKS":
        return None

    body = _path(root, "CONTRACTING_BODY", "ADDRESS_CONTRACTING_BODY")
    buyer = _direct_text(body, "OFFICIALNAME")
    buyer_id = _direct_text(body, "NATIONALID")
    title = _first_paragraph(_direct(object_contract, "TITLE"))
    description = _first_paragraph(_direct(object_contract, "SHORT_DESCR")) or title
    reference = _direct_text(object_contract, "REFERENCE_NUMBER")
    cpvs = _all_code_attributes(object_contract, "CPV_CODE")
    nuts = _all_code_attributes(object_contract, "NUTS")
    procedure = _procedure_code(root)
    deadline = _parse_source_datetime(_path_text(root, "PROCEDURE", "DATETIME_RECEIPT_TENDERS"))
    additional = _direct(root, "ADDITIONAL_CORE_DATA")
    first_publication = _direct_text(additional, "DATE_FIRST_PUBLICATION")
    source_updated = _parse_source_datetime(_direct_text(additional, "DATETIME_LAST_CHANGE"))
    item_updated = _parse_source_datetime(item_lastmod)
    updated = source_updated or item_updated
    human_url = _path_text(root, "CONTRACTING_BODY", "URL_DOCUMENT") or _direct_text(body, "URL_DOCUMENT")
    if not human_url:
        human_url = _text(_first_desc(root, "URL_DOCUMENT"))
    start_date = _path_text(object_contract, "OBJECT_DESCR", "DATE_START")
    end_date = _path_text(object_contract, "OBJECT_DESCR", "DATE_END")
    lot_division = _direct(object_contract, "LOT_DIVISION") is not None

    external_id = _semantic_key(
        dataset_id,
        buyer_id=buyer_id,
        buyer=buyer,
        reference=reference,
        title=title,
        description=description,
        cpvs=cpvs,
        nuts=nuts,
        first_publication=first_publication,
        procedure=procedure,
    )
    alias = f"{dataset_id}:{item_id}"
    return {
        "external_id": external_id,
        "procedure_id": external_id,
        "publication_aliases": [alias],
        "current_publication_alias": alias,
        "dataset_id": str(dataset_id),
        "item_id": str(item_id),
        "notice_url": str(notice_url or ""),
        "payload_family": "legacy_kerndaten",
        "root_family": root_name,
        "title": title,
        "description": description,
        "buyer": buyer,
        "buyer_national_id": buyer_id,
        "reference_number": reference,
        "cpv_codes": cpvs,
        "nuts_codes": nuts,
        "deadline": _utc(deadline),
        "first_published_at": first_publication,
        "source_updated_at": _utc(updated),
        "url": human_url or str(notice_url or ""),
        "procedure": procedure,
        "contract_type": "works",
        "lot_division": bool(lot_division),
        "start_date": start_date,
        "end_date": end_date,
        "was_visible": False,
    }


def _eforms_cpvs(elem):
    out = []
    if elem is None:
        return out
    for child in elem.iter():
        if _local(child.tag) != "ItemClassificationCode":
            continue
        list_name = str(child.attrib.get("listName") or "").strip().lower()
        if list_name and list_name != "cpv":
            continue
        value = _text(child)
        if value and value not in out:
            out.append(value)
    return out


def _eforms_organization_map(root):
    out = {}
    organizations = _first_desc(root, "Organizations")
    if organizations is None:
        return out
    for organization in list(organizations):
        if _local(organization.tag) != "Organization":
            continue
        company = _direct(organization, "Company")
        org_id = _path_text(company, "PartyIdentification", "ID")
        if not org_id:
            continue
        out[org_id] = {
            "name": _path_text(company, "PartyName", "Name"),
            "national_id": _path_text(company, "PartyLegalEntity", "CompanyID") or org_id,
        }
    return out


def _eforms_buyer(root):
    contracting = _first_desc(root, "ContractingParty")
    party = _direct(contracting, "Party") if contracting is not None else None
    buyer_ref = _path_text(party, "PartyIdentification", "ID")
    mapped = _eforms_organization_map(root).get(buyer_ref, {})
    return buyer_ref, str(mapped.get("name") or "").strip(), str(mapped.get("national_id") or "").strip()


def _eforms_human_url(root, fallback):
    for child in root.iter():
        if _local(child.tag) not in {"URI", "WebsiteURI", "BuyerProfileURI"}:
            continue
        value = _text(child)
        if value.startswith(("https://", "http://")):
            return value
    return str(fallback or "")


def _eforms_deadline(lot):
    process = _direct(lot, "TenderingProcess")
    period = _direct(process, "TenderSubmissionDeadlinePeriod") if process is not None else None
    if period is None:
        return None
    return _parse_eforms_datetime(_direct_text(period, "EndDate"), _direct_text(period, "EndTime"))


def _eforms_states(root, *, dataset_id, item_id, item_lastmod, notice_url):
    if _local(root.tag) != EFORMS_NOTICE_ROOT:
        return []
    project = _first_desc(root, "ProcurementProject")
    if project is None:
        raise RuntimeError(f"{SOURCE} eForms ContractNotice missing ProcurementProject; cursor not advanced")
    if _direct_text(project, "ProcurementTypeCode").lower() != "works":
        return []

    folder_id = _direct_text(root, "ContractFolderID")
    notice_id = _direct_text(root, "ID")
    issue = _parse_eforms_datetime(_direct_text(root, "IssueDate"), _direct_text(root, "IssueTime"))
    if not folder_id or not notice_id or issue is None:
        raise RuntimeError(f"{SOURCE} eForms Works notice missing ContractFolderID/ID/issue timestamp; cursor not advanced")

    lots = [child for child in root.iter() if _local(child.tag) == "ProcurementProjectLot"]
    if not lots:
        raise RuntimeError(f"{SOURCE} eForms Works notice contains no ProcurementProjectLot; cursor not advanced")

    _buyer_ref, buyer, buyer_national_id = _eforms_buyer(root)
    project_title = _direct_text(project, "Name")
    project_description = _direct_text(project, "Description") or project_title
    project_cpvs = _eforms_cpvs(project)
    human_url = _eforms_human_url(root, notice_url)
    process = _direct(root, "TenderingProcess") or _first_desc(root, "TenderingProcess")
    procedure = _direct_text(process, "ProcedureCode")
    alias = f"{dataset_id}:{item_id}"
    item_updated = _parse_source_datetime(item_lastmod)
    updated = max(value for value in (issue, item_updated) if value is not None)

    states = []
    for lot in lots:
        lot_id = _direct_text(lot, "ID")
        if not lot_id:
            raise RuntimeError(f"{SOURCE} eForms Works lot missing ID; cursor not advanced")
        lot_name = _direct_text(lot, "Name")
        cpvs = _eforms_cpvs(lot) or project_cpvs
        deadline = _eforms_deadline(lot)
        title = project_title
        if len(lots) > 1 and lot_name:
            title = f"{project_title} — {lot_name}" if project_title else lot_name
        external_id = f"{dataset_id}:eforms:{folder_id}:{lot_id}"
        states.append(
            {
                "external_id": external_id,
                "procedure_id": folder_id,
                "lot_id": lot_id,
                "publication_aliases": [alias],
                "current_publication_alias": alias,
                "dataset_id": str(dataset_id),
                "item_id": str(item_id),
                "notice_id": notice_id,
                "notice_url": str(notice_url or ""),
                "payload_family": "eforms_ubl_2_3",
                "root_family": EFORMS_NOTICE_ROOT,
                "title": title or lot_id,
                "description": project_description or title or lot_id,
                "buyer": buyer,
                "buyer_national_id": buyer_national_id,
                "reference_number": folder_id,
                "cpv_codes": cpvs,
                "nuts_codes": [],
                "deadline": _utc(deadline),
                "first_published_at": _utc(issue),
                "source_updated_at": _utc(updated),
                "url": human_url,
                "procedure": procedure,
                "contract_type": "works",
                "lot_division": len(lots) > 1,
                "lot_count": len(lots),
                "was_visible": False,
            }
        )
    return states


def _parse_notice(payload, **context):
    try:
        root = fromstring(payload)
    except Exception as exc:
        raise RuntimeError(f"{SOURCE} invalid notice XML; cursor not advanced") from exc
    root_name = _local(root.tag)
    if root_name in LEGACY_ACTIONABLE_ROOTS:
        state = _legacy_state(root, **context)
        return [] if state is None else [state]
    if root_name == EFORMS_NOTICE_ROOT:
        return _eforms_states(root, **context)
    if root_name.startswith("KD_") or root_name in EFORMS_NON_ACTIONABLE_ROOTS:
        return []
    raise RuntimeError(f"{SOURCE} unsupported notice root {root_name}; cursor not advanced")


def _merge_state(current, incoming):
    if current is None:
        return deepcopy(incoming)
    merged = deepcopy(current)
    aliases = []
    for value in list(current.get("publication_aliases") or []) + list(incoming.get("publication_aliases") or []):
        value = str(value or "").strip()
        if value and value not in aliases:
            aliases.append(value)
    current_time = _parse_source_datetime(current.get("source_updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
    incoming_time = _parse_source_datetime(incoming.get("source_updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
    if incoming_time >= current_time:
        merged.update(deepcopy(incoming))
    merged["publication_aliases"] = aliases
    merged["was_visible"] = bool(current.get("was_visible")) or bool(incoming.get("was_visible"))
    first_values = [
        str(value or "").strip()
        for value in (current.get("first_published_at"), incoming.get("first_published_at"))
        if str(value or "").strip()
    ]
    if first_values:
        merged["first_published_at"] = min(first_values)
    return merged


def _legacy_alias_index(tracked):
    """Map a legacy publication alias to one unambiguous canonical state key.

    A KDQ item id is publisher-local publication identity. Anonymous publishers
    may omit both REFERENCE_NUMBER and NATIONALID, so content-based identity is
    needed for first discovery. Once an alias has been observed, however, that
    alias is stronger continuity evidence than mutable title/description text.

    eForms aliases are deliberately excluded: one ContractNotice publication
    can contain several lots, so an alias alone is not a one-to-one key there.
    """
    candidates = {}
    for key, state in (tracked or {}).items():
        if not isinstance(state, dict) or state.get("payload_family") != "legacy_kerndaten":
            continue
        for alias in state.get("publication_aliases") or []:
            alias = str(alias or "").strip()
            if alias:
                candidates.setdefault(alias, set()).add(str(key))
    return {
        alias: next(iter(keys))
        for alias, keys in candidates.items()
        if len(keys) == 1
    }


def _reanchor_legacy_state(state, *, alias_index, tracked):
    if not isinstance(state, dict) or state.get("payload_family") != "legacy_kerndaten":
        return state
    matched = {
        alias_index[alias]
        for alias in state.get("publication_aliases") or []
        if alias in alias_index
    }
    if len(matched) != 1:
        return state
    canonical = next(iter(matched))
    previous = (tracked or {}).get(canonical) or {}
    anchored = deepcopy(state)
    anchored["external_id"] = canonical
    anchored["procedure_id"] = str(previous.get("procedure_id") or canonical)
    return anchored


def _deadline_status(state, now):
    deadline_text = str(state.get("deadline") or "").strip()
    if not deadline_text:
        return False, "deadline_missing"
    deadline = _parse_source_datetime(deadline_text)
    if deadline is None:
        return False, "deadline_invalid"
    if deadline <= now:
        return False, "deadline_elapsed"
    return True, "open"


def _observation(state, *, actionable, lifecycle_status, lifecycle_reason, lifecycle_only=False):
    cpvs = [str(code).strip() for code in state.get("cpv_codes", []) if str(code).strip()]
    nuts = [str(code).strip() for code in state.get("nuts_codes", []) if str(code).strip()]
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
        "value": "",
        "currency": "",
        "deadline": str(state.get("deadline") or ""),
        "publication_date": str(state.get("first_published_at") or "")[:10],
        "published_at": state.get("first_published_at") or None,
        "source_updated_at": state.get("source_updated_at") or None,
        "url": str(state.get("url") or state.get("notice_url") or ""),
        "market": "GLOBAL",
        "place": " | ".join(nuts),
        "source_status": str(state.get("root_family") or ""),
        "source_phase": "notice",
        "signal_type": "TENDER",
        "procurement_method": str(state.get("procedure") or ""),
        "contract_type": "works",
        "source_reference": str(state.get("current_publication_alias") or ""),
        "notice_identifier": str(state.get("item_id") or state.get("notice_id") or ""),
        "procedure_reference": str(state.get("reference_number") or state.get("procedure_id") or ""),
        "dataset_id": str(state.get("dataset_id") or ""),
        "publication_aliases": list(state.get("publication_aliases") or []),
        "payload_family": str(state.get("payload_family") or ""),
        "root_family": str(state.get("root_family") or ""),
        "buyer_national_id": str(state.get("buyer_national_id") or ""),
        "lot_id": str(state.get("lot_id") or ""),
        "lot_count": int(state.get("lot_count") or 1),
        "lot_division": bool(state.get("lot_division")),
        "start_date": str(state.get("start_date") or ""),
        "end_date": str(state.get("end_date") or ""),
        "attribution": ATTRIBUTION,
        "source_catalog_url": CATALOG_URL,
        "source_api_url": str(state.get("notice_url") or ""),
        "is_actionable": bool(actionable),
        "lifecycle_status": lifecycle_status,
        "lifecycle_reason": lifecycle_reason,
    }
    if lifecycle_only:
        row["_lifecycle_only"] = True
    return row


def _graph_access_urls(payload):
    out = []
    if not isinstance(payload, dict):
        return out
    for node in payload.get("@graph") or []:
        if not isinstance(node, dict):
            continue
        access = node.get("dcat:accessURL")
        candidates = access if isinstance(access, list) else [access]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            value = str(candidate.get("@id") or "").strip()
            if value and value not in out:
                out.append(value)
    return out


def _content_length(response):
    try:
        return int(response.headers.get("content-length") or 0)
    except (TypeError, ValueError):
        return 0


def _bounded_response_bytes(response, *, max_bytes, label):
    length = _content_length(response)
    if length and length > max_bytes:
        response.close()
        raise RuntimeError(f"{SOURCE} {label} exceeds max_resource_bytes={max_bytes}; cursor not advanced")
    out = bytearray()
    try:
        for chunk in response.iter_content(131072):
            if not chunk:
                continue
            out.extend(chunk)
            if len(out) > max_bytes:
                raise RuntimeError(f"{SOURCE} {label} exceeds max_resource_bytes={max_bytes}; cursor not advanced")
    finally:
        response.close()
    return bytes(out)


def _stream_kdq(response, *, max_bytes, max_items):
    length = _content_length(response)
    if length and length > max_bytes:
        response.close()
        raise RuntimeError(f"{SOURCE} KDQ exceeds max_kdq_bytes={max_bytes}; cursor not advanced")
    parser = XMLPullParser(events=("start", "end"))
    total = 0
    root_name = None
    items = []
    try:
        for chunk in response.iter_content(131072):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise RuntimeError(f"{SOURCE} KDQ exceeds max_kdq_bytes={max_bytes}; cursor not advanced")
            parser.feed(chunk)
            for event, elem in parser.read_events():
                if root_name is None and event == "start":
                    root_name = _local(elem.tag)
                    if root_name.lower() != "kdq":
                        raise RuntimeError(f"{SOURCE} unexpected KDQ root {root_name}; cursor not advanced")
                if event != "end" or _local(elem.tag).lower() != "item":
                    continue
                item_id = str(elem.attrib.get("id") or "").strip()
                lastmod = str(elem.attrib.get("lastmod") or "").strip()
                url = ""
                for child in list(elem):
                    if _local(child.tag).lower() == "url":
                        url = _text(child).strip()
                        break
                if not item_id or not lastmod or not url:
                    raise RuntimeError(f"{SOURCE} KDQ item missing id/lastmod/url; cursor not advanced")
                items.append({"id": item_id, "lastmod": lastmod, "url": url})
                if len(items) > max_items:
                    raise RuntimeError(f"{SOURCE} KDQ exceeds max_kdq_items={max_items}; cursor not advanced")
                elem.clear()
        parser.close()
    finally:
        response.close()
    if root_name is None:
        raise RuntimeError(f"{SOURCE} empty KDQ; cursor not advanced")
    return items


@dataclass
class AustriaKerndatenCursor:
    observed_through: str
    datasets: dict
    kdq_observed: dict
    tracked: dict

    @classmethod
    def empty(cls):
        return cls(observed_through="", datasets={}, kdq_observed={}, tracked={})

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
        datasets = payload.get("datasets") or {}
        kdq_observed = payload.get("kdq_observed") or {}
        tracked = payload.get("tracked") or {}
        if not isinstance(datasets, dict) or not isinstance(kdq_observed, dict) or not isinstance(tracked, dict):
            raise RuntimeError(f"invalid {SOURCE} cursor structure; cursor not advanced")
        return cls(
            observed_through=str(payload.get("observed_through") or ""),
            datasets=deepcopy(datasets),
            kdq_observed=deepcopy(kdq_observed),
            tracked=deepcopy(tracked),
        )

    def encode(self):
        return json.dumps(
            {
                "version": 1,
                "observed_through": self.observed_through,
                "datasets": self.datasets,
                "kdq_observed": self.kdq_observed,
                "tracked": self.tracked,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


class AustriaKerndatenConnector:
    def __init__(
        self,
        *,
        session=None,
        initial_lookback_days=60,
        overlap_hours=48,
        max_datasets=100,
        max_kdqs=150,
        max_kdq_bytes=32 * 1024 * 1024,
        max_kdq_items=100000,
        max_notice_bytes=4 * 1024 * 1024,
        max_notice_fetches_per_kdq=1000,
    ):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)
        self.initial_lookback_days = int(initial_lookback_days)
        self.overlap_hours = int(overlap_hours)
        self.max_datasets = int(max_datasets)
        self.max_kdqs = int(max_kdqs)
        self.max_kdq_bytes = int(max_kdq_bytes)
        self.max_kdq_items = int(max_kdq_items)
        self.max_notice_bytes = int(max_notice_bytes)
        self.max_notice_fetches_per_kdq = int(max_notice_fetches_per_kdq)

    def _catalog_dataset_ids(self):
        response = self.session.get(
            CATALOG_SEARCH,
            params={"q": "Kerndaten", "limit": self.max_datasets + 1},
            headers={**HEADERS, "Accept": "application/json"},
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            raise RuntimeError(f"{SOURCE} catalogue search malformed; cursor not advanced")
        try:
            count = int(result.get("count") or 0)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{SOURCE} catalogue count malformed; cursor not advanced") from exc
        if count > self.max_datasets:
            raise RuntimeError(f"{SOURCE} catalogue exceeds max_datasets={self.max_datasets}; cursor not advanced")
        rows = result.get("results") or []
        if not isinstance(rows, list):
            raise RuntimeError(f"{SOURCE} catalogue results malformed; cursor not advanced")
        ids = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            dataset_id = str(row.get("id") or "").strip()
            if dataset_id and dataset_id not in ids:
                ids.append(dataset_id)
        if count and len(ids) < count:
            raise RuntimeError(f"{SOURCE} catalogue results truncated; cursor not advanced")
        return ids

    def _dataset_urls(self, dataset_id):
        response = self.session.get(
            f"{CATALOG_DATASET}/{dataset_id}",
            headers={**HEADERS, "Accept": "application/ld+json"},
            timeout=45,
        )
        response.raise_for_status()
        return _graph_access_urls(response.json())

    def _discover(self, cursor):
        discovered = deepcopy(cursor.datasets)
        for dataset_id in self._catalog_dataset_ids():
            urls = self._dataset_urls(dataset_id)
            if urls:
                discovered[dataset_id] = {"urls": urls}
        kdq_count = sum(
            len((entry or {}).get("urls") or [])
            for entry in discovered.values()
            if isinstance(entry, dict)
        )
        if kdq_count > self.max_kdqs:
            raise RuntimeError(f"{SOURCE} discovery exceeds max_kdqs={self.max_kdqs}; cursor not advanced")
        if not discovered:
            raise RuntimeError(f"{SOURCE} discovered no KDQ datasets; cursor not advanced")
        return discovered

    def _notice_payload(self, url):
        response = self.session.get(
            url,
            headers={**HEADERS, "Accept": "application/xml,text/xml,*/*;q=0.5"},
            timeout=60,
            stream=True,
            allow_redirects=True,
        )
        response.raise_for_status()
        return _bounded_response_bytes(response, max_bytes=self.max_notice_bytes, label="notice")

    def _kdq_items(self, url):
        response = self.session.get(
            url,
            headers={**HEADERS, "Accept": "application/xml,text/xml,*/*;q=0.5"},
            timeout=60,
            stream=True,
            allow_redirects=True,
        )
        response.raise_for_status()
        return _stream_kdq(response, max_bytes=self.max_kdq_bytes, max_items=self.max_kdq_items)

    def fetch_incremental(self, *, watermark=None, now=None):
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        now = now.astimezone(timezone.utc)
        cursor = AustriaKerndatenCursor.decode(watermark)
        observed = _parse_source_datetime(cursor.observed_through)
        if observed is not None and observed > now + timedelta(minutes=5):
            raise RuntimeError(f"{SOURCE} cursor is in the future; cursor not advanced")

        datasets = self._discover(cursor)
        candidate_states = {}
        kdq_observed = deepcopy(cursor.kdq_observed)
        alias_index = _legacy_alias_index(cursor.tracked)
        successful_kdqs = 0
        last_errors = []

        for dataset_id, entry in datasets.items():
            urls = list((entry or {}).get("urls") or []) if isinstance(entry, dict) else []
            for kdq_url in urls:
                old_kdq_observed = _parse_source_datetime(kdq_observed.get(kdq_url))
                cutoff = (
                    old_kdq_observed - timedelta(hours=self.overlap_hours)
                    if old_kdq_observed is not None
                    else now - timedelta(days=self.initial_lookback_days)
                )
                try:
                    items = self._kdq_items(kdq_url)
                    selected = []
                    for item in items:
                        modified = _parse_source_datetime(item.get("lastmod"))
                        if modified is None:
                            raise RuntimeError(f"{SOURCE} KDQ item has invalid lastmod; cursor not advanced")
                        if modified >= cutoff:
                            selected.append(item)
                    if len(selected) > self.max_notice_fetches_per_kdq:
                        raise RuntimeError(
                            f"{SOURCE} KDQ requires {len(selected)} notice fetches > "
                            f"max_notice_fetches_per_kdq={self.max_notice_fetches_per_kdq}; cursor not advanced"
                        )

                    local_states = {}
                    for item in selected:
                        payload = self._notice_payload(item["url"])
                        states = _parse_notice(
                            payload,
                            dataset_id=dataset_id,
                            item_id=item["id"],
                            item_lastmod=item["lastmod"],
                            notice_url=item["url"],
                        )
                        for state in states:
                            state = _reanchor_legacy_state(
                                state,
                                alias_index=alias_index,
                                tracked=cursor.tracked,
                            )
                            key = state["external_id"]
                            local_states[key] = _merge_state(local_states.get(key), state)
                    for key, state in local_states.items():
                        candidate_states[key] = _merge_state(candidate_states.get(key), state)
                    kdq_observed[kdq_url] = _utc(now)
                    successful_kdqs += 1
                except Exception as exc:
                    last_errors.append(f"{kdq_url}: {type(exc).__name__}: {str(exc)}")
                    # Keep this KDQ's old watermark so a later run retries its window.
                    continue

        if successful_kdqs == 0:
            detail = "; ".join(last_errors[-3:])
            raise RuntimeError(f"{SOURCE} no KDQ completed successfully; cursor not advanced: {detail}")

        tracked = deepcopy(cursor.tracked)
        observations = []
        all_keys = set(tracked) | set(candidate_states)
        for key in sorted(all_keys):
            previous = tracked.get(key)
            incoming = candidate_states.get(key)
            if incoming is not None:
                incoming = _merge_state(previous, incoming)
                actionable, reason = _deadline_status(incoming, now)
                if actionable:
                    incoming["was_visible"] = True
                    changed = previous != incoming
                    tracked[key] = incoming
                    if changed or previous is None:
                        observations.append(
                            _observation(
                                incoming,
                                actionable=True,
                                lifecycle_status="open",
                                lifecycle_reason="future_submission_deadline",
                            )
                        )
                    continue

                if previous and previous.get("was_visible"):
                    incoming["was_visible"] = True
                    tracked[key] = incoming if reason in {"deadline_missing", "deadline_invalid"} else None
                    observations.append(
                        _observation(
                            incoming,
                            actionable=False,
                            lifecycle_status=reason,
                            lifecycle_reason=reason,
                            lifecycle_only=True,
                        )
                    )
                    if tracked.get(key) is None:
                        tracked.pop(key, None)
                else:
                    tracked.pop(key, None)
                continue

            if previous is None:
                continue
            actionable, reason = _deadline_status(previous, now)
            if actionable:
                continue
            if previous.get("was_visible"):
                observations.append(
                    _observation(
                        previous,
                        actionable=False,
                        lifecycle_status=reason,
                        lifecycle_reason=reason,
                        lifecycle_only=True,
                    )
                )
            if reason in {"deadline_missing", "deadline_invalid"}:
                tracked[key] = previous
            else:
                tracked.pop(key, None)

        next_cursor = AustriaKerndatenCursor(
            observed_through=_utc(now),
            datasets=datasets,
            kdq_observed=kdq_observed,
            tracked={key: value for key, value in tracked.items() if isinstance(value, dict)},
        )
        return observations, next_cursor.encode()


def fetch_austria_kerndaten_tenders(*, watermark=None, session=None, now=None):
    connector = AustriaKerndatenConnector(session=session)
    return connector.fetch_incremental(watermark=watermark, now=now)
