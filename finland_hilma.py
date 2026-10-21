"""Finland HILMA AVP national procurement enrichment.

HILMA's official AVP read API exposes Finnish public procurement notices through
an Azure Search-compatible endpoint. This connector intentionally targets the
national value-add above TED: Finnish works contract notices and procurement
plans, including below-EU-threshold publications that never reach TED.

The read API requires a free self-service subscription key. The key is never
stored in source code; set ``HILMA_API_KEY`` in the runtime environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from typing import Iterable

import requests


SOURCE = "FI_HILMA"
COUNTRY = "FIN"
SEARCH_ENDPOINT = "https://api.hankintailmoitukset.fi/avp/eformnotices/docs/search"
PUBLIC_SITE = "https://www.hankintailmoitukset.fi"
ATTRIBUTION = "HILMA / hankintailmoitukset.fi, Finland"
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1000
DEFAULT_OVERLAP_HOURS = 48

_SELECT_FIELDS = (
    "noticeId,titleFi,titleSv,titleEn,organisationNameFi,"
    "organisationNationalRegistrationNumber,descriptionFi,cpvCodes,mainType,"
    "datePublished,expirationDate,nutsCodes,procedureType,procurementTypeCode,"
    "estimatedValue,eFormsId,procedureId,procurementDocumentsUrl,sendingSystem"
)


def _text(value):
    return "" if value is None else str(value).strip()


def _utc(value):
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value):
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _cpvs(value):
    if isinstance(value, list):
        parts = value
    else:
        raw = _text(value)
        for separator in (";", "|", ","):
            raw = raw.replace(separator, " ")
        parts = raw.split()
    out = []
    for part in parts:
        code = "".join(ch for ch in _text(part) if ch.isdigit())[:8]
        if len(code) == 8 and code not in out:
            out.append(code)
    return out


def _title(row):
    return _text(row.get("titleFi")) or _text(row.get("titleSv")) or _text(row.get("titleEn"))


def _is_works(row):
    return _text(row.get("procurementTypeCode")).lower() == "works"


def _notice_id(row):
    value = row.get("noticeId")
    if isinstance(value, bool) or value in (None, ""):
        return ""
    return _text(value)


def _procedure_reference(row):
    return _text(row.get("procedureId")) or _text(row.get("eFormsId")) or _notice_id(row)


def _signal_type(row):
    return "PROCUREMENT_PLAN" if _text(row.get("mainType")) == "PlanNotices" else "TENDER"


def _human_url(row):
    eforms_id = _text(row.get("eFormsId"))
    if eforms_id:
        return f"{PUBLIC_SITE}/fi/notice/{eforms_id}"
    notice_id = _notice_id(row)
    return f"{PUBLIC_SITE}/fi/notice/{notice_id}" if notice_id else PUBLIC_SITE


def normalize_notice(row, *, now=None):
    """Normalize one AVP search row to ObraSignal's canonical observation shape."""
    if not isinstance(row, dict):
        raise ValueError("HILMA notice must be a mapping")
    external_id = _notice_id(row)
    if not external_id:
        raise ValueError("HILMA notice missing noticeId")
    if not _is_works(row):
        return None

    signal_type = _signal_type(row)
    published = _utc(row.get("datePublished"))
    deadline = _utc(row.get("expirationDate"))
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if signal_type == "TENDER":
        actionable = bool(deadline and deadline > now)
        lifecycle_status = "open" if actionable else "inactive"
        lifecycle_reason = "open" if actionable else ("deadline_elapsed" if deadline else "deadline_missing_or_invalid")
    else:
        actionable = False
        lifecycle_status = "planned"
        lifecycle_reason = "procurement_plan"

    cpvs = _cpvs(row.get("cpvCodes"))
    nuts = row.get("nutsCodes")
    if isinstance(nuts, list):
        place = " | ".join(_text(v) for v in nuts if _text(v))
    else:
        place = _text(nuts)

    estimated = row.get("estimatedValue")
    return {
        "source": SOURCE,
        "external_id": external_id,
        "title": _title(row),
        "description": _text(row.get("descriptionFi")),
        "buyer": _text(row.get("organisationNameFi")),
        "buyer_national_id": _text(row.get("organisationNationalRegistrationNumber")),
        "country": COUNTRY,
        "cpv": cpvs[0] if cpvs else "",
        "cpv_codes": cpvs,
        "taxonomy": "CPV" if cpvs else "",
        "category_code": cpvs[0] if cpvs else "",
        "contract_type": "works",
        "procurement_method": _text(row.get("procedureType")),
        "value": "" if estimated in (None, "") else str(estimated),
        # Do not infer currency from country when the search index does not
        # explicitly couple a currency field to estimatedValue.
        "currency": "",
        "deadline": _iso(deadline),
        "publication_date": _iso(published)[:10] if published else "",
        "published_at": _iso(published) or None,
        "source_updated_at": None,
        "url": _human_url(row),
        "market": "GLOBAL",
        "place": place,
        "signal_type": signal_type,
        "source_phase": "plan" if signal_type == "PROCUREMENT_PLAN" else "notice",
        "source_reference": external_id,
        "notice_identifier": _text(row.get("eFormsId")) or external_id,
        "procedure_reference": _procedure_reference(row),
        "procurement_documents_url": _text(row.get("procurementDocumentsUrl")),
        "sending_system": _text(row.get("sendingSystem")),
        "attribution": ATTRIBUTION,
        "source_catalog_url": PUBLIC_SITE,
        "source_api_url": SEARCH_ENDPOINT,
        "is_actionable": actionable,
        "lifecycle_status": lifecycle_status,
        "lifecycle_reason": lifecycle_reason,
    }


@dataclass(frozen=True)
class HilmaCursor:
    published_through: str = ""

    @classmethod
    def decode(cls, value):
        if not value:
            return cls()
        try:
            payload = json.loads(value)
        except Exception as exc:
            raise RuntimeError("invalid FI_HILMA cursor") from exc
        if not isinstance(payload, dict) or int(payload.get("version") or 1) != 1:
            raise RuntimeError("invalid FI_HILMA cursor")
        return cls(published_through=_text(payload.get("published_through")))

    def encode(self):
        return json.dumps({"version": 1, "published_through": self.published_through}, sort_keys=True, separators=(",", ":"))


class HilmaAVPConnector:
    def __init__(self, *, api_key=None, session=None, page_size=DEFAULT_PAGE_SIZE, max_pages=100, overlap_hours=DEFAULT_OVERLAP_HOURS):
        self.api_key = _text(api_key or os.getenv("HILMA_API_KEY"))
        self.session = session or requests.Session()
        self.page_size = int(page_size)
        self.max_pages = int(max_pages)
        self.overlap_hours = int(overlap_hours)
        if not self.api_key:
            raise RuntimeError("HILMA_API_KEY is required for FI_HILMA")
        if self.page_size < 1 or self.page_size > MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
        if self.max_pages < 1:
            raise ValueError("max_pages must be >= 1")
        if self.overlap_hours < 0:
            raise ValueError("overlap_hours must be >= 0")

    @property
    def headers(self):
        return {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ObraSignal HILMA connector/1.0 (+official AVP read API)",
        }

    def _search(self, *, main_type, since, skip):
        filters = ["procurementTypeCode eq 'works'", f"mainType eq '{main_type}'"]
        if since is not None:
            filters.append(f"datePublished ge {_iso(since)}")
        body = {
            "search": "*",
            "filter": " and ".join(filters),
            "top": self.page_size,
            "skip": int(skip),
            "count": True,
            "orderby": "datePublished asc, noticeId asc",
            "searchMode": "any",
            "queryType": "simple",
            "select": _SELECT_FIELDS,
        }
        response = self.session.post(SEARCH_ENDPOINT, headers=self.headers, json=body, timeout=60)
        response.raise_for_status()
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError("FI_HILMA returned invalid JSON") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
            raise RuntimeError("FI_HILMA returned invalid search envelope")
        rows = payload["value"]
        if len(rows) > self.page_size or any(not isinstance(row, dict) for row in rows):
            raise RuntimeError("FI_HILMA returned malformed page")
        return rows

    def _iter_type(self, *, main_type, since):
        seen = set()
        for page in range(self.max_pages):
            rows = self._search(main_type=main_type, since=since, skip=page * self.page_size)
            for row in rows:
                notice_id = _notice_id(row)
                if not notice_id:
                    raise RuntimeError("FI_HILMA row missing noticeId; cursor not advanced")
                if notice_id in seen:
                    raise RuntimeError(f"FI_HILMA duplicate noticeId {notice_id}; cursor not advanced")
                seen.add(notice_id)
                yield row
            if len(rows) < self.page_size:
                return
        raise RuntimeError(f"FI_HILMA exceeded max_pages={self.max_pages}; cursor not advanced")

    def fetch_incremental(self, *, watermark=None, now=None):
        cursor = HilmaCursor.decode(watermark)
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        since = _utc(cursor.published_through)
        if since is not None and self.overlap_hours:
            since = since - timedelta(hours=self.overlap_hours)

        observations = []
        max_published = _utc(cursor.published_through)
        seen_identity = set()
        for main_type in ("ContractNotices", "PlanNotices"):
            for row in self._iter_type(main_type=main_type, since=since):
                normalized = normalize_notice(row, now=now)
                if normalized is None:
                    continue
                identity = (normalized["signal_type"], normalized["external_id"])
                if identity in seen_identity:
                    continue
                seen_identity.add(identity)
                observations.append(normalized)
                published = _utc(row.get("datePublished"))
                if published and (max_published is None or published > max_published):
                    max_published = published

        next_cursor = HilmaCursor(published_through=_iso(max_published) if max_published else cursor.published_through).encode()
        return observations, next_cursor


def fetch_finland_hilma(*, watermark=None):
    return HilmaAVPConnector().fetch_incremental(watermark=watermark)
