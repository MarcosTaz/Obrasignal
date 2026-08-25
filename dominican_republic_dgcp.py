"""Dominican Republic DGCP OCDS construction procurement source.

The official DGCP API uses a two-step transport in live operation:
``/ocds/releases/all`` returns a paginated generic envelope containing OCID/detail
URL candidates, then ``/ocds/releases?ocid=...`` returns the OCDS ReleasePackage.
The ReleasePackage is preserved as history so one hydration can safely expose
canonical TENDER, AWARD and CONTRACT signals without N+1 lifecycle lookups.

Publisher documentation (Swagger 2.0):
https://datosabiertos.dgcp.gob.do/api-dgcp/docs/doc.json

The publisher documents Apache-2.0 reuse and an eight-hour Data Warehouse refresh
interval. Public discovery, detail, PACC, contract and bulk transports were
live-proven from GitHub Actions on 2026-08-25. Production promotion remains
separately gated until full-window pagination/completeness, sustainable hydration
volume and runtime composition are validated.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ocds_adapter import OCDSAPIConfig, normalize_ocds_record
from ocds_release_lifecycle import (
    OCDSReleasePackageConnector,
    merge_nonempty_mapping,
)


DGCP_API_ROOT = "https://datosabiertos.dgcp.gob.do/api-dgcp/v1"
DGCP_OCDS_RELEASES_URL = f"{DGCP_API_ROOT}/ocds/releases/all"
DGCP_OCDS_DETAIL_URL_TEMPLATE = f"{DGCP_API_ROOT}/ocds/releases?ocid={{ocid}}"
DGCP_PORTAL_URL = "https://datosabiertos.dgcp.gob.do/"
DGCP_LICENSE = "Apache-2.0"
DGCP_ATTRIBUTION = "Dirección General de Contrataciones Públicas (DGCP) — República Dominicana"


DGCP_CONFIG = OCDSAPIConfig(
    source="DO_DGCP",
    country="DOM",
    search_url=DGCP_OCDS_RELEASES_URL,
    page_param="page",
    page_size_param="limit",
    # The publisher documents a maximum limit of 1000. A smaller page keeps
    # response and per-request hydration pressure bounded while completeness is
    # validated. The whole temporal window still fails closed above the bound.
    page_size=200,
    max_pages_per_window=100,
    window_days=1,
    max_windows_per_sync=14,
    initial_lookback_days=7,
    overlap_days=1,
    market="GLOBAL",
    timeout=45,
    record_url_template=DGCP_OCDS_DETAIL_URL_TEMPLATE,
    hydrate_records=True,
    max_hydrations_per_window=250,
)


def dgcp_search_params(start, end):
    """Return only publisher-documented date filters.

    DGCP does not document a server-side ``works`` parameter on the OCDS
    discovery endpoint, so construction admission happens on the publisher-native
    OCDS ``mainProcurementCategory`` after bounded detail hydration. We
    deliberately do not substitute keyword matching.
    """
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }


def _release_history(record):
    if not isinstance(record, dict):
        return []
    compiled = record.get("compiledRelease")
    if isinstance(compiled, dict):
        return [compiled]
    releases = record.get("releases")
    if not isinstance(releases, list):
        return []
    return sorted(
        (release for release in releases if isinstance(release, dict)),
        key=lambda release: str(release.get("date") or ""),
    )


def _latest_tender_release(record):
    candidates = [
        release
        for release in _release_history(record)
        if isinstance(release.get("tender"), dict)
    ]
    return max(candidates, key=lambda release: str(release.get("date") or ""), default=None)


def _works_context(record):
    release = _latest_tender_release(record)
    tender = release.get("tender") if isinstance(release, dict) else None
    if not isinstance(tender, dict):
        return None, None
    if str(tender.get("mainProcurementCategory") or "").strip().lower() != "works":
        return None, None
    ocid = str(record.get("ocid") or release.get("ocid") or "").strip()
    if not ocid:
        return None, None
    base = normalize_ocds_record(
        {"ocid": ocid, "compiledRelease": release},
        source="DO_DGCP",
        country="DOM",
        market="GLOBAL",
        require_active_tender=False,
    )
    return release, base


def _decorate(item):
    item["url"] = item.get("url") or DGCP_PORTAL_URL
    item["license"] = DGCP_LICENSE
    item["attribution"] = DGCP_ATTRIBUTION
    item["source_dataset"] = "DGCP API — OCDS releases"
    item["source_modified"] = True
    return item


def normalize_dgcp_process(record):
    """Normalize one active DGCP works tender without inventing taxonomy maps."""
    release, base = _works_context(record)
    if not base or not isinstance(release, dict):
        return None
    tender = release.get("tender")
    if str(tender.get("status") or "").strip().lower() != "active":
        return None
    base["signal_type"] = "TENDER"
    return _decorate(base)


def _entity_versions(record, key):
    """Return merged partial OCDS entities plus their latest observation date."""
    merged = {}
    observed = {}
    for release in _release_history(record):
        release_date = str(release.get("date") or "").strip()
        values = release.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, dict):
                continue
            identity = str(value.get("id") or "").strip()
            if not identity:
                continue
            merged[identity] = merge_nonempty_mapping(merged.get(identity), value)
            if release_date:
                observed[identity] = release_date
    return {
        identity: (value, observed.get(identity, ""))
        for identity, value in merged.items()
    }


def _supplier_names(award):
    suppliers = award.get("suppliers") if isinstance(award, dict) else None
    if not isinstance(suppliers, list):
        return []
    names = []
    for supplier in suppliers:
        if not isinstance(supplier, dict):
            continue
        name = str(supplier.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _lifecycle_common(base, *, signal_type, external_id, source_reference, observed_at):
    row = {
        "source": "DO_DGCP",
        "signal_type": signal_type,
        "external_id": external_id,
        "title": base.get("title") or "",
        "description": base.get("description") or "",
        "buyer": base.get("buyer") or "",
        "country": "DOM",
        "value": "",
        "currency": "",
        "deadline": "",
        "target_date": "",
        "publication_date": observed_at[:10] if observed_at else "",
        "published_at": observed_at or None,
        "source_updated_at": observed_at or None,
        "url": base.get("url") or DGCP_PORTAL_URL,
        "taxonomy": base.get("taxonomy") or "",
        "category_code": base.get("category_code") or "",
        "contract_type": "works",
        "source_reference": source_reference,
        "ocid": base.get("ocid") or "",
        "cpv": base.get("cpv") or "",
        "classification_scheme": base.get("classification_scheme") or "",
    }
    return _decorate(row)


def normalize_dgcp_lifecycle(record):
    """Normalize AWARD/CONTRACT signals from the same hydrated works package."""
    _, base = _works_context(record)
    if not base:
        return []
    ocid = str(base.get("ocid") or "").strip()
    if not ocid:
        return []

    award_versions = _entity_versions(record, "awards")
    contract_versions = _entity_versions(record, "contracts")
    rows = []

    for award_id, (award, observed_at) in award_versions.items():
        award_date = str(award.get("date") or "").strip()
        row = _lifecycle_common(
            base,
            signal_type="AWARD",
            external_id=f"{ocid}:award:{award_id}",
            source_reference=award_id,
            observed_at=observed_at or award_date,
        )
        if award_date:
            row["publication_date"] = award_date[:10]
            row["published_at"] = award_date
        value = award.get("value") if isinstance(award.get("value"), dict) else {}
        row["value"] = str(value.get("amount") or "").strip()
        row["currency"] = str(value.get("currency") or "").strip()
        row["source_status"] = str(award.get("status") or "").strip()
        row["award_id"] = award_id
        row["suppliers"] = _supplier_names(award)
        if row["suppliers"]:
            row["supplier"] = row["suppliers"][0]
        rows.append(row)

    for contract_id, (contract, observed_at) in contract_versions.items():
        row = _lifecycle_common(
            base,
            signal_type="CONTRACT",
            external_id=f"{ocid}:contract:{contract_id}",
            source_reference=contract_id,
            observed_at=observed_at,
        )
        value = contract.get("value") if isinstance(contract.get("value"), dict) else {}
        period = contract.get("period") if isinstance(contract.get("period"), dict) else {}
        row["title"] = str(contract.get("title") or row["title"] or "").strip()
        row["value"] = str(value.get("amount") or "").strip()
        row["currency"] = str(value.get("currency") or "").strip()
        row["target_date"] = str(period.get("startDate") or "").strip()
        row["contract_end_date"] = str(period.get("endDate") or "").strip()
        row["source_status"] = str(contract.get("status") or "").strip()
        row["contract_id"] = contract_id
        row["award_id"] = str(contract.get("awardID") or "").strip()
        linked = award_versions.get(row["award_id"])
        suppliers = _supplier_names(linked[0]) if linked else []
        row["suppliers"] = suppliers
        if suppliers:
            row["supplier"] = suppliers[0]
        rows.append(row)

    return rows


def normalize_dgcp_signals(record):
    """Emit canonical tender + lifecycle signals from one hydrated works OCID."""
    rows = []
    tender = normalize_dgcp_process(record)
    if tender:
        rows.append(tender)
    rows.extend(normalize_dgcp_lifecycle(record))
    return rows


def dgcp_connector(*, session=None):
    return OCDSReleasePackageConnector(
        DGCP_CONFIG,
        params_factory=dgcp_search_params,
        session=session,
    )


def fetch_dgcp_processes(*, watermark=None, now=None, connector=None):
    """Compatibility path: return only active TENDER signals."""
    client = connector or dgcp_connector()
    return client.fetch_incremental(
        normalize_dgcp_process,
        watermark=watermark,
        now=now or datetime.now(timezone.utc),
    )


def fetch_dgcp_signals(*, watermark=None, now=None, connector=None):
    """Return TENDER/AWARD/CONTRACT signals from one bounded OCDS sync."""
    client = connector or dgcp_connector()
    return client.fetch_incremental_many(
        normalize_dgcp_signals,
        watermark=watermark,
        now=now or datetime.now(timezone.utc),
    )
