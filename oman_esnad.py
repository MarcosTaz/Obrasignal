"""Oman Esnad/Tender Board public upcoming-tender early-signal connector.

Coverage is a LIMITED HIGH-VALUE SLICE: the official public `Upcoming Tender`
view only. These rows are pre-publication procurement signals and normalize to
ObraSignal's canonical PROCUREMENT_PLAN type. This module does not claim access
to every internal preparation-plan field and does not enable runtime ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re
from typing import Iterable

import requests


SOURCE = "OM_ESNAD"
SOURCE_URL = "https://etendering.tenderboard.gov.om/product/publicDash?viewFlag=UpcomingTenders"
COUNTRY = "OMN"
MAX_HTML_BYTES = 5_000_000

_WS = re.compile(r"\s+")
_UPCOMING_ID = re.compile(r"^\[\s*(\d+)\s*\]\s*-\s*(.+)$")
_EN_TITLE = re.compile(
    r"\b(?:construction|infrastructure|roads?|bridges?|building|buildings|renovation|rehabilitation|civil works|maintenance of (?:a |the )?building)\b",
    re.I,
)
_AR_TITLE_TERMS = (
    "إنشاء", "انشاء", "تشييد", "بناء", "بناية", "مبنى", "مباني", "شوارع",
    "طرق", "جسور", "تأهيل", "إعادة تأهيل", "اعادة تأهيل", "صيانة المواقف",
    "صيانة مبنى", "صيانة المبنى", "توسعة", "تطوير موقع", "أعمال مدنية",
    "اعمال مدنية",
)
_CONSTRUCTION_CATEGORIES = (
    "construction and maintenance",
    "construction of ports roads bridges railways dams and maintenance",
    "building construction",
    "المقاولات العمرانيه والصيانة",
    "المقاولات العمرانية والصيانة",
    "مقاولات المواني والطرق والجسور والسكك الحديدية والسدود والصيانة",
    "مقاولات الكهروميكانيكية والإتصالات والصيانة",
    "مقاولات الكهروميكانيكية والاتصالات والصيانة",
)


class OmanEsnadSourceError(RuntimeError):
    """Transport or publisher-contract error; never convert to zero signals."""


@dataclass(frozen=True)
class UpcomingTender:
    internal_id: str
    tender_no: str
    title: str
    entity: str
    category: str


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data):
        if not self._skip_depth and self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(_clean(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            self._cell = None


def _clean(value: str) -> str:
    return _WS.sub(" ", str(value or "")).strip()


def parse_upcoming_tenders(html: str) -> list[UpcomingTender]:
    if not isinstance(html, str) or not html.strip():
        raise OmanEsnadSourceError("empty Esnad upcoming-tender HTML")
    if len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise OmanEsnadSourceError("Esnad response exceeds safety limit")
    if "Upcoming Tender" not in html and "المناقصات القادمة" not in html:
        raise OmanEsnadSourceError("Esnad upcoming-tender marker missing")

    parser = _TableParser()
    parser.feed(html)
    rows: list[UpcomingTender] = []
    for cells in parser.rows:
        if len(cells) < 5:
            continue
        match = _UPCOMING_ID.match(cells[1])
        if not match:
            continue
        internal_id, tender_no = match.groups()
        title = _clean(cells[2])
        entity = _clean(cells[3])
        category = _clean(cells[4])
        if not title or not entity or not tender_no:
            raise OmanEsnadSourceError(f"incomplete Esnad upcoming row for {internal_id}")
        rows.append(UpcomingTender(internal_id, _clean(tender_no), title, entity, category))
    if not rows:
        raise OmanEsnadSourceError("Esnad source contract changed: no upcoming rows parsed")
    ids = [r.internal_id for r in rows]
    if len(ids) != len(set(ids)):
        raise OmanEsnadSourceError("duplicate Esnad upcoming internal identity")
    return rows


def is_construction_relevant(tender: UpcomingTender) -> bool:
    category = tender.category.casefold()
    if any(term.casefold() in category for term in _CONSTRUCTION_CATEGORIES):
        return True
    title = tender.title
    if _EN_TITLE.search(title):
        return True
    return any(term in title for term in _AR_TITLE_TERMS)


def normalize_upcoming(tender: UpcomingTender) -> dict:
    if not tender.internal_id.isdigit():
        raise OmanEsnadSourceError(f"invalid Esnad internal id: {tender.internal_id!r}")
    return {
        "source": SOURCE,
        "signal_type": "PROCUREMENT_PLAN",
        "external_id": tender.internal_id,
        "source_reference": tender.tender_no,
        "title": tender.title,
        "description": None,
        "buyer": tender.entity,
        "country": COUNTRY,
        "publication_date": None,
        "published_at": None,
        "source_updated_at": None,
        "deadline": None,
        "url": SOURCE_URL,
        "taxonomy": "OM_ESNAD_UPCOMING_CATEGORY_TITLE_V1",
        "category_code": tender.category or None,
        "place": "Oman",
        "construction_relevant": True,
        "coverage_scope": "LIMITED_HIGH_VALUE_SLICE_OM_ESNAD_UPCOMING_TENDERS",
        "upcoming_tender_no": tender.tender_no,
    }


def normalize_construction_plans(tenders: Iterable[UpcomingTender]) -> list[dict]:
    return [normalize_upcoming(t) for t in tenders if is_construction_relevant(t)]


def fetch_upcoming_tenders(*, session=None, timeout: float = 25.0) -> list[UpcomingTender]:
    client = session or requests
    try:
        response = client.get(
            SOURCE_URL,
            timeout=timeout,
            headers={"User-Agent": "ObraSignal/1.0 (+official-source-validation)"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise OmanEsnadSourceError(f"Esnad fetch failed: {exc}") from exc
    return parse_upcoming_tenders(response.text)


def fetch_normalized_construction_plans(*, session=None, timeout: float = 25.0) -> list[dict]:
    rows = fetch_upcoming_tenders(session=session, timeout=timeout)
    normalized = normalize_construction_plans(rows)
    if not normalized:
        raise OmanEsnadSourceError("Esnad fetch succeeded but construction classifier admitted zero plans")
    return normalized


class OmanEsnadUpcomingConnector:
    """Registry-candidate adapter for official public pre-publication signals."""

    source = SOURCE

    def __init__(self, *, session=None, timeout: float = 25.0):
        self.session = session
        self.timeout = timeout

    def fetch(self) -> list[dict]:
        return fetch_normalized_construction_plans(session=self.session, timeout=self.timeout)
