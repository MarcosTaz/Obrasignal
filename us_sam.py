"""SAM.gov federal construction opportunities connector.

Production contract (validated against official SAM.gov/GSA sources, 2026-08-25):
- Contract Opportunities bulk extract is public and redirects to the official
  ``falextracts.s3.amazonaws.com`` publisher bucket;
- current full CSV has a stable 47-column publisher schema;
- ``NoticeId`` is the durable notice identity; solicitation number is preserved
  as procedure/reference metadata and is not assumed globally unique;
- construction admission is publisher-native NAICS sector 23 (23xxxx), never a
  keyword heuristic;
- the full CSV is a daily active snapshot. Missing records are therefore not
  declared cancelled: unknown disappearance fails closed;
- award fields are not tender value. ObraSignal never maps ``Award$`` onto an
  open opportunity value;
- SAM.gov public API v2 is a future freshness accelerator. It requires an API
  key and provides only the latest active version; production v0.1 therefore
  uses the no-key public bulk snapshot as the dependable base path.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json

import requests

SOURCE = "US_SAM"
COUNTRY = "USA"
BULK_URL = (
    "https://sam.gov/api/prod/fileextractservices/v1/api/download/"
    "Contract%20Opportunities/datagov/ContractOpportunitiesFullCSV.csv?privacy=Public"
)
CATALOG_URL = "https://sam.gov/data-services/Contract%20Opportunities/datagov?privacy=Public"
PUBLIC_SITE = "https://sam.gov/opportunities"
ATTRIBUTION = "U.S. General Services Administration — SAM.gov Contract Opportunities"
HEADERS = {
    "Accept": "text/csv,application/octet-stream;q=0.9,*/*;q=0.1",
    "User-Agent": "ObraSignal SAM.gov connector/1.0 (+official public-data ingestion)",
}

CSV_FIELDS = (
    "NoticeId", "Title", "Sol#", "Department/Ind.Agency", "CGAC", "Sub-Tier",
    "FPDS Code", "Office", "AAC Code", "PostedDate", "Type", "BaseType",
    "ArchiveType", "ArchiveDate", "SetASideCode", "SetASide", "ResponseDeadLine",
    "NaicsCode", "ClassificationCode", "PopStreetAddress", "PopCity", "PopState",
    "PopZip", "PopCountry", "Active", "AwardNumber", "AwardDate", "Award$",
    "Awardee", "PrimaryContactTitle", "PrimaryContactFullname", "PrimaryContactEmail",
    "PrimaryContactPhone", "PrimaryContactFax", "SecondaryContactTitle",
    "SecondaryContactFullname", "SecondaryContactEmail", "SecondaryContactPhone",
    "SecondaryContactFax", "OrganizationType", "State", "City", "ZipCode",
    "CountryCode", "AdditionalInfoLink", "Link", "Description",
)

ACTIONABLE_NOTICE_TYPES = frozenset({
    "Presolicitation",
    "Solicitation",
    "Combined Synopsis/Solicitation",
    "Sources Sought",
})


def _text(value):
    return str(value or "").strip()


def _is_construction(row):
    code = _text(row.get("NaicsCode"))
    return len(code) == 6 and code.isdigit() and code.startswith("23")


def _parse_datetime(value):
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value):
    if not value:
        return ""
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _observation(row):
    if not _is_construction(row):
        raise RuntimeError(f"{SOURCE} non-construction row passed NAICS gate; cursor not advanced")
    notice_id = _text(row.get("NoticeId"))
    if not notice_id:
        raise RuntimeError(f"{SOURCE} construction row missing NoticeId; cursor not advanced")
    notice_type = _text(row.get("Type"))
    posted = _parse_datetime(row.get("PostedDate"))
    deadline = _parse_datetime(row.get("ResponseDeadLine"))
    active = _text(row.get("Active")).casefold() == "yes"
    actionable = active and notice_type in ACTIONABLE_NOTICE_TYPES and (deadline is None or deadline > datetime.now(timezone.utc))
    place = " | ".join(x for x in (
        _text(row.get("PopCity")), _text(row.get("PopState")), _text(row.get("PopCountry"))
    ) if x)
    contacts = []
    for prefix in ("PrimaryContact", "SecondaryContact"):
        item = {
            "title": _text(row.get(prefix + "Title")),
            "name": _text(row.get(prefix + "Fullname")),
            "email": _text(row.get(prefix + "Email")),
            "phone": _text(row.get(prefix + "Phone")),
            "fax": _text(row.get(prefix + "Fax")),
        }
        if any(item.values()):
            contacts.append(item)
    link = _text(row.get("Link")) or PUBLIC_SITE
    return {
        "source": SOURCE,
        "external_id": notice_id,
        "title": _text(row.get("Title")),
        "description": _text(row.get("Description")),
        "buyer": _text(row.get("Department/Ind.Agency")),
        "buyer_subtier": _text(row.get("Sub-Tier")),
        "buyer_office": _text(row.get("Office")),
        "country": COUNTRY,
        "cpv": "",
        "taxonomy": "NAICS",
        "category_code": _text(row.get("NaicsCode")),
        "cpv_codes": [],
        "naics_code": _text(row.get("NaicsCode")),
        "classification_code": _text(row.get("ClassificationCode")),
        "value": "",
        "currency": "",
        "deadline": _iso(deadline),
        "publication_date": _text(row.get("PostedDate")),
        "published_at": _iso(posted) or None,
        "source_updated_at": None,
        "url": link,
        "market": "GLOBAL",
        "place": place,
        "source_status": _text(row.get("Active")),
        "source_phase": notice_type,
        "signal_type": "TENDER",
        "contract_type": "works",
        "source_reference": notice_id,
        "notice_identifier": notice_id,
        "procedure_reference": _text(row.get("Sol#")),
        "notice_type": notice_type,
        "base_type": _text(row.get("BaseType")),
        "archive_type": _text(row.get("ArchiveType")),
        "archive_date": _text(row.get("ArchiveDate")),
        "set_aside_code": _text(row.get("SetASideCode")),
        "set_aside": _text(row.get("SetASide")),
        "contacts": contacts,
        "additional_info_link": _text(row.get("AdditionalInfoLink")),
        "attribution": ATTRIBUTION,
        "source_catalog_url": CATALOG_URL,
        "source_api_url": BULK_URL,
        "is_actionable": bool(actionable),
        "lifecycle_status": "open" if active else "inactive",
        "lifecycle_reason": "publisher_active_snapshot" if active else "publisher_inactive",
    }


@dataclass
class SAMCursor:
    etag: str = ""
    last_modified: str = ""

    @classmethod
    def decode(cls, value):
        if value in (None, ""):
            return cls()
        try:
            payload = json.loads(value)
        except Exception as exc:
            raise RuntimeError(f"invalid {SOURCE} cursor; cursor not advanced") from exc
        if not isinstance(payload, dict) or int(payload.get("version") or 0) != 1:
            raise RuntimeError(f"invalid {SOURCE} cursor version; cursor not advanced")
        return cls(etag=_text(payload.get("etag")), last_modified=_text(payload.get("last_modified")))

    def encode(self):
        return json.dumps({"version": 1, "etag": self.etag, "last_modified": self.last_modified}, sort_keys=True, separators=(",", ":"))


class SAMGovConnector:
    def __init__(self, *, session=None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    def fetch(self, *, watermark=None):
        cursor = SAMCursor.decode(watermark)
        headers = dict(HEADERS)
        if cursor.etag:
            headers["If-None-Match"] = cursor.etag
        if cursor.last_modified:
            headers["If-Modified-Since"] = cursor.last_modified
        response = self.session.get(BULK_URL, headers=headers, timeout=180, stream=True)
        if response.status_code == 304:
            return [], cursor.encode()
        response.raise_for_status()
        etag = _text(response.headers.get("ETag"))
        last_modified = _text(response.headers.get("Last-Modified"))
        # Requests owns response.raw and may close that object while a wrapper is
        # still iterating after the publisher redirect. Use Requests' supported
        # streaming iterator instead. Re-add line terminators so csv can preserve
        # quoted multiline descriptions without materialising the ~250 MB extract.
        def decoded_lines():
            first = True
            for chunk in response.iter_lines(decode_unicode=False):
                if isinstance(chunk, bytes):
                    line = chunk.decode("utf-8", errors="replace")
                else:
                    line = str(chunk)
                if first:
                    line = line.lstrip("\ufeff")
                    first = False
                yield line + "\n"

        # SAM descriptions can exceed Python csv's conservative 128 KiB default.
        csv.field_size_limit(64 * 1024 * 1024)
        reader = csv.DictReader(decoded_lines())
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            raise RuntimeError(
                f"{SOURCE} CSV schema drift: expected {len(CSV_FIELDS)} publisher columns; cursor not advanced"
            )
        observations = []
        for row in reader:
            if None in row:
                raise RuntimeError(f"{SOURCE} malformed CSV row exceeds publisher schema; cursor not advanced")
            if not _is_construction(row):
                continue
            observations.append(_observation(row))
        if not observations:
            raise RuntimeError(f"{SOURCE} active bulk snapshot contained no NAICS-23 construction opportunities; cursor not advanced")
        return observations, SAMCursor(etag=etag, last_modified=last_modified).encode()


def fetch_us_sam_tenders(*, watermark=None, session=None):
    return SAMGovConnector(session=session).fetch(watermark=watermark)
