"""Latvia Procurement Monitoring Bureau (IUB) official daily JSON connector.

From 2026 the IUB open-data service publishes one JSON file per publication day.
The current notice is the top-level object; a republication may embed the full
previous notice in ``clonedFrom``. Actionable competition deadlines are lot-level
BT-131 fields and must not be confused with review/complaint deadlines.
"""
from datetime import date, datetime, timezone
import re
from zoneinfo import ZoneInfo

from official_json_bulk_adapter import OfficialJSONBulkAdapter, OfficialJSONBulkConfig


LV_IUB_ROOT = "https://open.iub.gov.lv/data/notice"
LV_IUB_METADATA_URL = "https://open.iub.gov.lv/data/publiskie_iepirkumi_metadata.json"
LV_IUB_LICENSE = "https://creativecommons.org/publicdomain/zero/1.0/legalcode.lv"
LV_IUB_ATTRIBUTION = "Iepirkumu uzraudzības birojs (IUB) — Publiskie iepirkumi"
LV_IUB_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal procurement connector/1.0 (+official open-data client)",
}
RIGA = ZoneInfo("Europe/Riga")


def iub_daily_url(day):
    if not isinstance(day, date):
        raise ValueError("publication day must be a date")
    return f"{LV_IUB_ROOT}/{day:%Y/%m/%d-%m-%Y}.json"


def _text(value):
    return "" if value is None else str(value).strip()


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _parse_now(value):
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _latvia_deadline(date_value, time_value):
    date_text = _text(date_value)
    time_text = _text(time_value)
    if not date_text or not time_text:
        return None
    parsed_date = None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            parsed_date = datetime.strptime(date_text[:10], fmt).date()
            break
        except ValueError:
            pass
    if parsed_date is None:
        return None
    parsed_time = None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            parsed_time = datetime.strptime(time_text, fmt).time()
            break
        except ValueError:
            pass
    if parsed_time is None:
        return None
    local = datetime.combine(parsed_date, parsed_time, tzinfo=RIGA)
    return local.astimezone(timezone.utc)


def _normalized_cpv(value):
    raw = _text(value)
    digits = re.sub(r"\D", "", raw)
    # CPV carries eight classification digits plus an optional check digit.
    return digits[:8] if len(digits) >= 8 else ""


def _place(lot, organization):
    place = _dict(lot.get("place"))
    values = []
    for value in (
        place.get("placePerformanceRegionDescription"),
        place.get("placePerformanceCity"),
        place.get("placePerformanceCountrySubCode"),
        place.get("placePerformanceCountryCode"),
        organization.get("city"),
        organization.get("nutsCode"),
    ):
        text = _text(value)
        if text and text not in values:
            values.append(text)
    return " | ".join(values)


def _clone_identifier(notice):
    clone = notice.get("clonedFrom")
    if isinstance(clone, dict):
        return _text(clone.get("identifier"))
    return ""


def _canonical_lot_id(notice, lot):
    process_id = _text(notice.get("procurementProcedureIdentifier"))
    notice_id = _text(notice.get("identifier"))
    sequence = _text(lot.get("sequenceNumber"))
    lot_id = _text(lot.get("id"))
    if process_id and sequence:
        return f"{process_id}:lot:{sequence}"
    if process_id:
        return f"{process_id}:notice:{notice_id or 'unknown'}:lot:{lot_id or 'unknown'}"
    if notice_id:
        return f"{notice_id}:lot:{sequence or lot_id or 'unknown'}"
    return ""


def normalize_iub_notice(notice, *, publication_day, now=None):
    """Return actionable TENDER rows, one per open lot.

    Planning/result/contract-modification notices are intentionally excluded from
    the tender-centric runtime. ``clonedFrom`` is provenance only: the nested old
    notice is never normalized recursively.
    """
    if not isinstance(notice, dict):
        return []
    if _text(notice.get("formType")).lower() != "competition":
        return []

    current = _parse_now(now)
    if current is None:
        raise RuntimeError("LV_IUB requires a valid current timestamp")

    project = _dict(notice.get("procurementProject"))
    process = _dict(notice.get("tenderingProcess"))
    terms = _dict(notice.get("tenderingTerms"))
    organization = _dict(notice.get("organizationData"))
    notice_id = _text(notice.get("identifier"))
    process_id = _text(notice.get("procurementProcedureIdentifier"))
    procurement_reference = _text(project.get("procurementIdentifier"))
    nature = _text(notice.get("mainNatureType") or project.get("mainNatureType"))
    notice_cpv_raw = _text(notice.get("cpvType"))
    clone_id = _clone_identifier(notice)
    source_url = _text(terms.get("submissionURL") or process.get("documentsURL"))
    buyer = _text(organization.get("name"))

    rows = []
    for lot in _list(notice.get("lots")):
        if not isinstance(lot, dict):
            continue
        lot_process = _dict(lot.get("tenderingProcess"))
        deadline = _latvia_deadline(
            lot_process.get("deadlineReceiptTendersEndDate"),
            lot_process.get("deadlineReceiptTendersEndTime"),
        )
        if deadline is None or deadline <= current:
            continue
        external_id = _canonical_lot_id(notice, lot)
        if not external_id:
            continue

        lot_info = _dict(lot.get("additionalInformation"))
        lot_terms = _dict(lot.get("tenderingTerms"))
        lot_cpv_raw = _text(lot.get("cpvType") or notice_cpv_raw)
        cpv = _normalized_cpv(lot_cpv_raw)
        description = _text(lot.get("description") or project.get("description"))
        title = _text(lot.get("name") or notice.get("name"))
        value = _text(lot_info.get("estimatedValue"))
        submission_url = _text(terms.get("submissionURL") or source_url)
        eu_funded = lot_terms.get("isEuFunded")

        rows.append({
            "source": "LV_IUB",
            "external_id": external_id,
            "title": title,
            "description": description,
            "buyer": buyer,
            "country": "LVA",
            "cpv": cpv,
            "cpv_raw": lot_cpv_raw,
            "taxonomy": "CPV" if cpv else "",
            "category_code": cpv,
            "value": value,
            # No currency is inferred. The sampled/open-data contract does not
            # provide an explicit currency alongside lot estimatedValue.
            "currency": "",
            "deadline": deadline.isoformat().replace("+00:00", "Z"),
            "publication_date": publication_day.isoformat(),
            "published_at": publication_day.isoformat(),
            "source_updated_at": publication_day.isoformat(),
            "url": submission_url or _text(process.get("documentsURL")),
            "market": "GLOBAL",
            "place": _place(lot, organization),
            "source_status": "",
            "source_phase": _text(notice.get("noticeType")),
            "signal_type": "TENDER",
            "procurement_method": _text(process.get("procedureType")),
            "contract_type": nature,
            "source_reference": notice_id,
            "notice_identifier": notice_id,
            "procurement_procedure_identifier": process_id,
            "procurement_reference": procurement_reference,
            "lot_sequence": _text(lot.get("sequenceNumber")),
            "lot_id": _text(lot.get("id")),
            "notice_type": _text(notice.get("noticeType")),
            "form_type": _text(notice.get("formType")),
            "is_republication": bool(clone_id),
            "cloned_from_identifier": clone_id,
            "eu_funded": eu_funded,
            "nuts_code": _text(organization.get("nutsCode")),
            "buyer_identifier": _text(organization.get("identifier")),
            "contact_point": notice.get("contactPoint") if isinstance(notice.get("contactPoint"), dict) else None,
            "license": LV_IUB_LICENSE,
            "attribution": LV_IUB_ATTRIBUTION,
            "source_dataset": "IUB Publiskie iepirkumi — daily JSON notices",
            "source_modified": True,
        })
    return rows


def build_iub_connector(*, session=None):
    config = OfficialJSONBulkConfig(
        source="LV_IUB",
        country="LVA",
        url_factory=iub_daily_url,
        initial_lookback_days=3,
        overlap_days=1,
        max_days_per_sync=7,
        publication_lag_days=1,
        timeout=45,
        market="GLOBAL",
    )
    return OfficialJSONBulkAdapter(
        config,
        normalizer=normalize_iub_notice,
        session=session,
        headers=LV_IUB_HEADERS,
    )


def fetch_iub_tenders(*, watermark=None, now=None, connector=None):
    client = connector or build_iub_connector()
    return client.fetch_incremental(watermark=watermark, now=now)
