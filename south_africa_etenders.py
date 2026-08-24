"""South Africa National Treasury eTenders OCDS connector.

Uses the official public OCDS Release API. The API returns compiled releases and
supports bounded date-window pagination via PageNumber/PageSize/dateFrom/dateTo,
so transport is delegated to the shared OCDSAPIConnector. This module only owns
South-Africa-specific source configuration, local-field preservation and the
commercial open-tender gate.
"""
from datetime import datetime, timezone
from urllib.parse import quote

from ocds_adapter import OCDSAPIConfig, OCDSAPIConnector, normalize_ocds_record


ZA_ETENDERS_API = "https://ocds-api.etenders.gov.za/api/OCDSReleases"
ZA_ETENDERS_RELEASE_ROOT = f"{ZA_ETENDERS_API}/release"
ZA_ETENDERS_LICENSE = "https://opendatacommons.org/licenses/pddl/1-0/111"
ZA_ETENDERS_PUBLICATION_POLICY = "https://data.etenders.gov.za/Home/LearnMore"
ZA_ETENDERS_ATTRIBUTION = "National Treasury of South Africa — eTenders / OCDS"
ZA_ETENDERS_COVERAGE_NOTE = (
    "National Treasury eTenders open data reflects procurement data shared with "
    "National Treasury and is not guaranteed to be a complete record of every "
    "South African public procurement process."
)


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


def _future_deadline(value, now=None):
    deadline = _parse_dt(value)
    current = _parse_dt(now or datetime.now(timezone.utc))
    return bool(deadline and current and deadline > current)


def _release(record):
    if not isinstance(record, dict):
        return {}
    compiled = record.get("compiledRelease")
    if isinstance(compiled, dict):
        return compiled
    releases = record.get("releases")
    if isinstance(releases, list) and releases:
        candidates = [row for row in releases if isinstance(row, dict)]
        return max(candidates, key=lambda row: str(row.get("date") or ""), default={})
    return {}


def normalize_za_release(record, *, now=None):
    """Normalize only currently actionable tenders from a compiled ZA release."""
    release = _release(record)
    tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
    if str(tender.get("status") or "").strip().lower() != "active":
        return None
    tender_period = tender.get("tenderPeriod") if isinstance(tender.get("tenderPeriod"), dict) else {}
    if not _future_deadline(tender_period.get("endDate"), now):
        return None

    item = normalize_ocds_record(
        record,
        source="ZA_ETENDERS",
        country="ZAF",
        market="GLOBAL",
        require_active_tender=True,
    )
    if not item:
        return None

    ocid = str(item.get("ocid") or release.get("ocid") or "").strip()
    if ocid:
        item["url"] = f"{ZA_ETENDERS_RELEASE_ROOT}/{quote(ocid, safe='')}"

    # The National Treasury implementation exposes useful local extensions that
    # are not represented by the generic OCDS normalizer. Preserve them without
    # pretending they are standard OCDS fields.
    province = str(tender.get("province") or "").strip()
    delivery_location = str(tender.get("deliveryLocation") or "").strip()
    item["place"] = delivery_location or province or item.get("place") or ""
    item["province"] = province
    item["delivery_location"] = delivery_location
    item["source_category"] = str(tender.get("category") or "").strip()
    item["special_conditions"] = str(tender.get("specialConditions") or "").strip()
    item["briefing_session"] = tender.get("briefingSession") if isinstance(tender.get("briefingSession"), dict) else None
    item["contact_person"] = tender.get("contactPerson") if isinstance(tender.get("contactPerson"), dict) else None
    item["license"] = ZA_ETENDERS_LICENSE
    item["publication_policy"] = ZA_ETENDERS_PUBLICATION_POLICY
    item["attribution"] = ZA_ETENDERS_ATTRIBUTION
    item["coverage_note"] = ZA_ETENDERS_COVERAGE_NOTE
    item["source_dataset"] = "National Treasury eTenders OCDS"
    return item


def _params(start, end):
    # Official OpenAPI accepts date-time strings and documents YYYY-MM-DD examples.
    # Endpoints behave as date-bounded release filters; one-day windows keep
    # pagination bounded and overlap is handled by the shared cursor logic.
    return {"dateFrom": start.isoformat(), "dateTo": end.isoformat()}


def build_za_connector(*, session=None):
    config = OCDSAPIConfig(
        source="ZA_ETENDERS",
        country="ZAF",
        search_url=ZA_ETENDERS_API,
        page_param="PageNumber",
        page_size_param="PageSize",
        page_size=500,
        max_pages_per_window=100,
        window_days=1,
        max_windows_per_sync=31,
        initial_lookback_days=3,
        overlap_days=1,
        market="GLOBAL",
        timeout=45,
        hydrate_records=False,
    )
    return OCDSAPIConnector(config, params_factory=_params, session=session)


def fetch_za_tenders(*, watermark=None, now=None, connector=None):
    client = connector or build_za_connector()
    normalizer = lambda record: normalize_za_release(record, now=now)
    return client.fetch_incremental(normalizer, watermark=watermark, now=now)
