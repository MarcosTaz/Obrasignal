"""Ecuador SERCOP official OCDS bulk + record connector.

Discovery uses the official monthly JSON ZIP export, never keyword search. Only
explicit OCDS ``works`` candidates are hydrated by OCID. Commercial actionability
requires an active tender and a valid future deadline; SERCOP CPC classifications
are preserved natively and are never rewritten as CPV.
"""
from datetime import datetime, timezone
from urllib.parse import quote

from ocds_adapter import normalize_ocds_record
from ocds_bulk_adapter import OCDSMonthlyBulkConfig, OCDSMonthlyBulkConnector


SOURCE = "EC_SERCOP"
SERCOP_BULK = (
    "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/download"
    "?type=json&year={year}&month={month}&method=all"
)
SERCOP_RECORD = "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/api/record"
SERCOP_PROCESS_ROOT = "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/ocds"
SERCOP_LICENSE = "https://creativecommons.org/licenses/by/3.0/ec/"
SERCOP_PUBLICATION_POLICY = (
    "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/documentos/"
    "politica-publicacion-SERCOP-OCDS.pdf"
)
SERCOP_ATTRIBUTION = "Servicio Nacional de Contratación Pública (SERCOP), Ecuador"


class SERCOPBulkRecordConnector(OCDSMonthlyBulkConnector):
    """Source-specific type over the reusable monthly OCDS bulk transport."""


def _parse_dt(value):
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


def _latest_release(record):
    if not isinstance(record, dict):
        return {}
    compiled = record.get("compiledRelease")
    if isinstance(compiled, dict):
        return compiled
    releases = record.get("releases")
    if not isinstance(releases, list):
        return {}
    candidates = [row for row in releases if isinstance(row, dict)]
    return max(candidates, key=lambda row: str(row.get("date") or ""), default={})


def _is_works_candidate(_package, release):
    tender = release.get("tender") if isinstance(release, dict) and isinstance(release.get("tender"), dict) else {}
    return str(tender.get("mainProcurementCategory") or "").strip().lower() == "works"


def _deadline_state(tender, now):
    status = str(tender.get("status") or "").strip().lower()
    period = tender.get("tenderPeriod") if isinstance(tender.get("tenderPeriod"), dict) else {}
    deadline = _parse_dt(period.get("endDate"))
    current = _parse_dt(now or datetime.now(timezone.utc))
    if status != "active":
        return False, status or "inactive", f"publisher tender status is {status or 'missing'}"
    if deadline is None:
        return False, "deadline_missing", "active tender has no valid submission deadline"
    if current is None or deadline <= current:
        return False, "deadline_expired", "publisher tender deadline has passed"
    return True, "active", "publisher reports active works tender with future deadline"


def normalize_sercop_record(record, *, now=None):
    release = _latest_release(record)
    tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
    if str(tender.get("mainProcurementCategory") or "").strip().lower() != "works":
        return None

    ocid = str(record.get("ocid") or release.get("ocid") or "").strip()
    if not ocid:
        return None
    actionable, lifecycle_status, lifecycle_reason = _deadline_state(tender, now)

    item = normalize_ocds_record(
        record,
        source=SOURCE,
        country="ECU",
        market="GLOBAL",
        require_active_tender=False,
    )
    if not item:
        return None

    tender_id = str(tender.get("id") or "").strip()
    title = str(tender.get("title") or "").strip()
    description = str(tender.get("description") or "").strip()
    if description and (not title or title == tender_id):
        item["title"] = description
    item["description"] = description or item.get("description") or ""

    period = tender.get("tenderPeriod") if isinstance(tender.get("tenderPeriod"), dict) else {}
    start = str(period.get("startDate") or "").strip()
    if start:
        item["publication_date"] = start[:10]

    item["external_id"] = ocid
    item["ocid"] = ocid
    item["url"] = f"{SERCOP_PROCESS_ROOT}/{quote(ocid, safe='')}"
    item["cpv"] = ""
    item["taxonomy"] = "CPC"
    if str(item.get("classification_scheme") or "").upper() != "CPC":
        item["category_code"] = ""
    item["contract_type"] = "works"
    item["is_actionable"] = actionable
    item["lifecycle_status"] = lifecycle_status
    item["lifecycle_reason"] = lifecycle_reason
    item["license"] = str(record.get("_package_license") or SERCOP_LICENSE)
    item["publication_policy"] = str(record.get("_package_publication_policy") or SERCOP_PUBLICATION_POLICY)
    item["attribution"] = SERCOP_ATTRIBUTION
    item["source_dataset"] = "Contrataciones Abiertas Ecuador — OCDS"
    item["source_api_url"] = f"{SERCOP_RECORD}?ocid={quote(ocid, safe='')}"
    item["source_package_published_at"] = record.get("_package_published_date")
    item["ocds_version"] = record.get("_package_version")

    if not actionable:
        item["_lifecycle_only"] = True
    return item


def build_sercop_connector(*, session=None, overlap_months=1):
    config = OCDSMonthlyBulkConfig(
        source=SOURCE,
        country="ECU",
        bulk_url_template=SERCOP_BULK,
        record_url=SERCOP_RECORD,
        market="GLOBAL",
        overlap_months=overlap_months,
        max_packages_per_file=250000,
        max_hydrations_per_sync=500,
        timeout=90,
        user_agent="ObraSignal SERCOP connector/1.0 (+official open-data ingestion)",
    )
    return SERCOPBulkRecordConnector(
        config,
        candidate_selector=_is_works_candidate,
        normalizer=normalize_sercop_record,
        session=session,
    )


def fetch_sercop_tenders(*, watermark=None, now=None, connector=None):
    client = connector or build_sercop_connector()
    return client.fetch_incremental(watermark=watermark, now=now)
