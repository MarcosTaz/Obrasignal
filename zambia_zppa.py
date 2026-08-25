"""Zambia ZPPA OCDS public-works tender slice.

Publisher: Zambia Public Procurement Authority (ZPPA).
Transport: Open Contracting Partnership Data Registry mirror of the official
ZPPA OCDS dataset. The mirror is used because it exposes bounded yearly JSONL
snapshots while preserving ZPPA data provenance and CC BY 4.0 licensing.

This connector intentionally emits only currently actionable public-works
tenders. It does not claim complete e-GP/front-end parity or award/contract
coverage even though those lifecycle objects exist upstream.
"""
from datetime import datetime, timezone

from ocds_adapter import normalize_ocds_record
from ocds_jsonl_snapshot import OCDSJSONLGzipConfig, OCDSJSONLGzipSnapshotConnector


SOURCE = "ZM_ZPPA"
ZM_ZPPA_DATA_URL = "https://data.open-contracting.org/en/publication/3/download?name={year}.jsonl.gz"
ZM_ZPPA_OFFICIAL_SOURCE = "https://www.zppa.org.zm/record-packages"
ZM_ZPPA_PUBLICATION_POLICY = "https://www.zppa.org.zm/ocds-publication-policy"
ZM_ZPPA_LICENSE = "https://creativecommons.org/licenses/by/4.0/"
ZM_ZPPA_ATTRIBUTION = "Zambia Public Procurement Authority (ZPPA) — OCDS"
ZM_ZPPA_COVERAGE_NOTE = (
    "ZPPA OCDS data is an official public-procurement dataset mirrored by the "
    "Open Contracting Partnership Data Registry. ZPPA record packages can be "
    "updated as a contracting process evolves, and published OCDS counts may "
    "differ from the e-GP front-end; this slice therefore does not claim complete "
    "real-time national coverage."
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


def _release(record):
    if not isinstance(record, dict):
        return {}
    compiled = record.get("compiledRelease")
    if isinstance(compiled, dict):
        return compiled
    releases = record.get("releases")
    if isinstance(releases, list):
        candidates = [row for row in releases if isinstance(row, dict)]
        return max(candidates, key=lambda row: str(row.get("date") or ""), default={})
    return {}


def _is_active_public_works(tender, *, now=None):
    if not isinstance(tender, dict):
        return False
    if str(tender.get("status") or "").strip().lower() != "active":
        return False
    category = str(tender.get("mainProcurementCategory") or "").strip().lower()
    if category != "works":
        return False
    tender_period = tender.get("tenderPeriod") if isinstance(tender.get("tenderPeriod"), dict) else {}
    deadline = _parse_dt(tender_period.get("endDate"))
    current = _parse_dt(now or datetime.now(timezone.utc))
    return bool(deadline and current and deadline > current)


def normalize_zm_release(record, *, now=None):
    """Normalize an active Zambian works tender using native OCDS classification."""
    release = _release(record)
    tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
    if not _is_active_public_works(tender, now=now):
        return None

    item = normalize_ocds_record(
        record,
        source=SOURCE,
        country="ZMB",
        market="GLOBAL",
        require_active_tender=True,
    )
    if not item:
        return None

    item["license"] = ZM_ZPPA_LICENSE
    item["publication_policy"] = ZM_ZPPA_PUBLICATION_POLICY
    item["attribution"] = ZM_ZPPA_ATTRIBUTION
    item["official_source"] = ZM_ZPPA_OFFICIAL_SOURCE
    item["source_dataset"] = "ZPPA Open Contracting Data Standard"
    item["coverage_note"] = ZM_ZPPA_COVERAGE_NOTE
    item["construction_filter"] = "OCDS tender.mainProcurementCategory=works"
    item["transport_mirror"] = "Open Contracting Partnership Data Registry"
    return item


def build_zm_connector(*, session=None):
    config = OCDSJSONLGzipConfig(
        source=SOURCE,
        country="ZMB",
        url_template=ZM_ZPPA_DATA_URL,
        market="GLOBAL",
        timeout=60,
        max_compressed_bytes=32 * 1024 * 1024,
        max_uncompressed_bytes=192 * 1024 * 1024,
        max_records=250_000,
    )
    return OCDSJSONLGzipSnapshotConnector(config, session=session)


def fetch_zm_tenders(*, watermark=None, now=None, connector=None):
    """Fetch the current-year snapshot.

    ``watermark`` is accepted for runtime contract compatibility but is not used
    to skip a snapshot: ZPPA can revise an older monthly record package as the
    same procurement process advances. Reprocessing by stable OCID is therefore
    intentional and idempotent at ObraSignal persistence/deduplication layers.
    """
    del watermark
    client = connector or build_zm_connector()
    normalizer = lambda record: normalize_zm_release(record, now=now)
    return client.fetch_snapshot(normalizer, now=now)
