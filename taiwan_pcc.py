"""Prepared Taiwan PCC bounded early-signal connector.

This module is intentionally source-specific. Taiwan's Public Construction
Commission publishes several daily XML snapshots with strong pre-tender and
contract-performance semantics, but the raw publisher payload contract has not
been live-proven from this environment. Therefore this connector is PREPARED,
not production-enabled: callers must provide/verify concrete source URLs before
runtime promotion.

Identity policy:
- require and preserve the native tender/case number as ``source_reference`` and
  ``lineage_key``;
- never synthesize procurement identity from mutable title/buyer text;
- keep one signal per semantic stage using the same tender/case identity;
- repeated snapshots upsert idempotently via (source, signal_type, external_id).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import unicodedata
import xml.etree.ElementTree as ET

import requests

SOURCE = "TW_PCC"
COUNTRY = "TWN"
DEFAULT_TIMEOUT = 45


@dataclass(frozen=True)
class PCCSnapshotSource:
    dataset_id: int
    name: str
    signal_type: str
    url: str | None


PCC_SOURCES = (
    PCCSnapshotSource(6574, "procurement_notice", "PROCUREMENT_PLAN", None),
    PCCSnapshotSource(
        7260,
        "public_viewing_announcement",
        "PROCUREMENT_PLAN",
        "https://web.pcc.gov.tw/tps/tp/OpenData/downloadTpReadOpenDataFile",
    ),
    PCCSnapshotSource(7261, "public_recruitment_announcement", "MARKET_DIALOGUE", None),
    PCCSnapshotSource(
        7264,
        "large_procurement_suppliers_in_performance",
        "CONTRACT",
        "https://web.pcc.gov.tw/peems/lapeem/lapeemGeneralPolit/downLoadOpenData",
    ),
)


def _norm_key(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    return re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", text)


def _text(value) -> str:
    return "" if value is None else str(value).strip()


FIELD_ALIASES = {
    "case_number": {_norm_key(x) for x in ("標案案號", "Tender case number", "Tender number", "Case number", "case_no", "caseno", "tender_no", "tenderno")},
    "title": {_norm_key(x) for x in ("標案名稱", "Tender name", "Project name", "Case name", "projectname", "tendername")},
    "buyer": {_norm_key(x) for x in ("機關名稱", "Agency name", "Organization name", "organizationname", "agencyname")},
    "method": {_norm_key(x) for x in ("招標方式", "Tendering method", "tenderingmethod")},
    "scheduled_month": {_norm_key(x) for x in ("預定招標年月", "Scheduled tender year and month", "scheduledtenderyearandmonth")},
    "announcement_count": {_norm_key(x) for x in ("公告次數", "The number of announcements", "announcementcount")},
    "event_date": {_norm_key(x) for x in ("公開閱覽日期", "公開徵求日期", "Date of public solicitation", "Public viewing date", "公告日期", "Award announcement date", "The date of tender award announcement")},
    "procurement_nature": {_norm_key(x) for x in ("採購性質", "Procurement nature", "procurementnature")},
    "purchase_amount": {_norm_key(x) for x in ("採購金額", "Purchase amount", "purchaseamount")},
    "vendor_code": {_norm_key(x) for x in ("廠商代碼", "Vendor code", "vendorcode")},
    "vendor_name": {_norm_key(x) for x in ("廠商名稱", "Vendor name", "vendorname")},
    "award_amount": {_norm_key(x) for x in ("得標金額", "The amount of the winning bid", "awardamount")},
    "performance_start": {_norm_key(x) for x in ("履約起始日期", "Commencement Date of Performance for Tender Award Notification", "performancestart")},
    "performance_end": {_norm_key(x) for x in ("履約完成日期", "Completion date of tender notice", "performanceend")},
}


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _row_mapping(element: ET.Element) -> dict[str, str]:
    values = {}
    for child in list(element):
        if len(list(child)):
            continue
        key = _norm_key(_strip_namespace(child.tag))
        if key:
            values[key] = _text(child.text)
    return values


def _field(mapping: dict[str, str], name: str) -> str:
    aliases = FIELD_ALIASES[name]
    for key, value in mapping.items():
        if key in aliases and _text(value):
            return _text(value)
    return ""


def _candidate_rows(root: ET.Element):
    seen = set()
    for element in root.iter():
        mapping = _row_mapping(element)
        if len(mapping) < 2 or not (_field(mapping, "case_number") or _field(mapping, "title")):
            continue
        identity = tuple(sorted(mapping.items()))
        if identity in seen:
            continue
        seen.add(identity)
        yield mapping


def parse_snapshot_xml(payload: bytes | str) -> list[dict[str, str]]:
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    if not payload or not payload.strip():
        raise RuntimeError("TW_PCC snapshot was empty")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise RuntimeError("TW_PCC snapshot was invalid XML") from exc
    rows = list(_candidate_rows(root))
    if not rows:
        raise RuntimeError("TW_PCC snapshot contained no recognizable procurement rows")
    return rows


def _stable_external_id(signal_type: str, case_number: str) -> str:
    return f"{signal_type.lower()}:{case_number}"


def _scheduled_target(value: str) -> str:
    digits = re.findall(r"\d+", value or "")
    if len(digits) >= 2:
        year, month = int(digits[0]), int(digits[1])
        if year < 1911:
            year += 1911
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}-01"
    return ""


def normalize_pcc_row(mapping: dict[str, str], *, source: PCCSnapshotSource, observed_at=None):
    case_number = _field(mapping, "case_number")
    if not case_number:
        # The audited PCC datasets advertise a publisher-native tender/case
        # number. Reject rows that lack it rather than fabricating unstable
        # identity from mutable title/buyer fields.
        return None
    title = _field(mapping, "title")
    buyer = _field(mapping, "buyer")
    observed = observed_at or datetime.now(timezone.utc).isoformat()
    event_date = _field(mapping, "event_date")
    scheduled = _field(mapping, "scheduled_month")
    procurement_nature = _field(mapping, "procurement_nature")
    amount = _field(mapping, "award_amount") or _field(mapping, "purchase_amount")
    return {
        "source": SOURCE,
        "signal_type": source.signal_type,
        "external_id": _stable_external_id(source.signal_type, case_number),
        "source_reference": case_number,
        "lineage_key": case_number,
        "title": title,
        "buyer": buyer,
        "country": COUNTRY,
        "publication_date": event_date,
        "published_at": event_date or None,
        # PCC catalogue freshness is daily, but observation time is not the
        # same thing as a publisher-declared update timestamp. Keep that
        # distinction explicit; signal_store owns first/last observation time.
        "source_updated_at": None,
        "_observed_at": observed,
        "target_date": _scheduled_target(scheduled),
        "taxonomy": "TW_PCC_PROCUREMENT_NATURE" if procurement_nature else "",
        "category_code": procurement_nature,
        "procurement_method": _field(mapping, "method"),
        "value": amount,
        "currency": "TWD" if amount else "",
        "vendor_code": _field(mapping, "vendor_code"),
        "vendor_name": _field(mapping, "vendor_name"),
        "performance_start": _field(mapping, "performance_start"),
        "performance_end": _field(mapping, "performance_end"),
        "announcement_count": _field(mapping, "announcement_count"),
        "native_dataset": source.name,
        "native_dataset_id": source.dataset_id,
        "url": f"https://data.gov.tw/en/datasets/{source.dataset_id}",
    }


class TaiwanPCCPreparedConnector:
    def __init__(self, *, sources=PCC_SOURCES, session=None, timeout=DEFAULT_TIMEOUT):
        self.sources = tuple(sources)
        self.session = session or requests.Session()
        self.timeout = int(timeout)

    def fetch_snapshot(self, *, observed_at=None):
        records = []
        for source in self.sources:
            if not source.url:
                raise RuntimeError(
                    f"TW_PCC dataset {source.dataset_id} ({source.name}) has no live-verified raw URL; connector remains prepared, not production-ready"
                )
            response = self.session.get(source.url, timeout=self.timeout)
            response.raise_for_status()
            for mapping in parse_snapshot_xml(response.content):
                record = normalize_pcc_row(mapping, source=source, observed_at=observed_at)
                if record:
                    records.append(record)
        return records


def prepared_sources():
    return {source.dataset_id: source for source in PCC_SOURCES}


def production_gate_reasons():
    reasons = []
    missing = [str(source.dataset_id) for source in PCC_SOURCES if not source.url]
    if missing:
        reasons.append("raw_url_unverified:" + ",".join(missing))
    reasons.append("live_payload_contract_unverified")
    reasons.append("runtime_not_enabled")
    return tuple(reasons)
