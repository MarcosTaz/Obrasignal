"""Ecuador SERCOP official OCDS rolling bulk connector.

SERCOP's keyword search API cannot represent the complete procurement universe
because a search term is mandatory. The official public bulk download is therefore
the corpus source. It exposes rolling month-level ZIPs containing OCDS
ReleasePackages; the record API remains the canonical detail link for each OCID.
"""
from datetime import datetime, timezone
from urllib.parse import quote

from ocds_adapter import normalize_ocds_record
from official_zip_json_snapshot_adapter import (
    OfficialZipJSONSnapshotAdapter,
    RollingSnapshotConfig,
)


EC_SERCOP_BASE = "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA"
EC_SERCOP_RECORD_API = f"{EC_SERCOP_BASE}/api/record"
EC_SERCOP_LICENSE = "https://creativecommons.org/licenses/by/3.0/ec/"
EC_SERCOP_PUBLICATION_POLICY = f"{EC_SERCOP_BASE}/documentos/politica-publicacion-SERCOP-OCDS.pdf"
EC_SERCOP_ATTRIBUTION = "Servicio Nacional de Contratación Pública (SERCOP) — Ecuador"


def sercop_bulk_url(year, month):
    return f"{EC_SERCOP_BASE}/download?type=json&year={int(year)}&month={int(month)}&method=all"


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


def _latest_release(package):
    if not isinstance(package, dict):
        return {}
    releases = package.get("releases")
    if not isinstance(releases, list):
        return {}
    candidates = [release for release in releases if isinstance(release, dict)]
    return max(candidates, key=lambda release: str(release.get("date") or ""), default={})


def _party_place(release):
    buyer = release.get("buyer") if isinstance(release.get("buyer"), dict) else {}
    buyer_id = str(buyer.get("id") or "").strip()
    parties = release.get("parties") if isinstance(release.get("parties"), list) else []
    for party in parties:
        if not isinstance(party, dict):
            continue
        if buyer_id and str(party.get("id") or "").strip() != buyer_id:
            continue
        address = party.get("address") if isinstance(party.get("address"), dict) else {}
        parts = []
        for key in ("streetAddress", "locality", "region", "postalCode", "countryName"):
            value = address.get(key)
            if isinstance(value, dict):
                value = value.get("name") or value.get("description")
            text = str(value or "").strip()
            if text and text not in parts:
                parts.append(text)
        return " | ".join(parts), party.get("contactPoint") if isinstance(party.get("contactPoint"), dict) else None
    return "", None


def normalize_sercop_package(package, *, now=None):
    """Emit only genuinely actionable SERCOP tenders from one ReleasePackage."""
    release = _latest_release(package)
    tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
    if str(tender.get("status") or "").strip().lower() != "active":
        return None

    tender_period = tender.get("tenderPeriod") if isinstance(tender.get("tenderPeriod"), dict) else {}
    deadline = _parse_dt(tender_period.get("endDate"))
    current = _parse_dt(now or datetime.now(timezone.utc))
    if not deadline or not current or deadline <= current:
        return None

    item = normalize_ocds_record(
        package,
        source="EC_SERCOP",
        country="ECU",
        market="GLOBAL",
        require_active_tender=True,
    )
    if not item:
        return None

    ocid = str(item.get("ocid") or release.get("ocid") or "").strip()
    if not ocid:
        return None
    item["url"] = f"{EC_SERCOP_RECORD_API}?ocid={quote(ocid, safe='')}"

    place, contact = _party_place(release)
    if place:
        item["place"] = place
    item["buyer_contact"] = contact
    item["license"] = str(package.get("license") or EC_SERCOP_LICENSE).strip()
    item["publication_policy"] = str(package.get("publicationPolicy") or EC_SERCOP_PUBLICATION_POLICY).strip()
    item["attribution"] = EC_SERCOP_ATTRIBUTION
    item["snapshot_published_at"] = str(package.get("publishedDate") or "").strip() or None
    item["source_dataset"] = "SERCOP Ecuador OCDS rolling monthly bulk"
    return item


def build_sercop_connector(*, session=None):
    config = RollingSnapshotConfig(
        source="EC_SERCOP",
        timezone_name="America/Guayaquil",
        lookback_months=2,
        refresh_after_local_hour=6,
        timeout=90,
        max_compressed_bytes=32 * 1024 * 1024,
        max_uncompressed_bytes=192 * 1024 * 1024,
        max_zip_entries=2,
    )
    return OfficialZipJSONSnapshotAdapter(
        config,
        url_factory=sercop_bulk_url,
        normalizer=normalize_sercop_package,
        session=session,
    )


def fetch_sercop_tenders(*, watermark=None, now=None, connector=None):
    client = connector or build_sercop_connector()
    return client.fetch_incremental(watermark=watermark, now=now)
