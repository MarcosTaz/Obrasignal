"""UAE Ministry of Finance public federal procurement opportunity connector.

Coverage is intentionally a LIMITED HIGH-VALUE SLICE: current federal business
opportunities publicly listed by the Ministry of Finance. It is not Dubai or Abu
Dhabi procurement coverage and it is not runtime-enabled here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
import re
from typing import Iterable
from urllib.parse import urljoin

import requests


SOURCE = "AE_MOF_DPP"
SOURCE_URL = "https://mof.gov.ae/en/public-finance/government-procurement/current-business-opportunities/"
COUNTRY = "ARE"
MAX_HTML_BYTES = 5_000_000
MAX_PAGES = 10

_WS = re.compile(r"\s+")
_RFQ = re.compile(r"^\d{3,}$")
_EN_STRONG = re.compile(
    r"\b(?:design\s+and\s+build|design\s*&\s*build|construction|civil\s+works|building\s+works|road\s+works|bridge\s+works|renovation|rehabilitation|fit[- ]?out\s+works)\b",
    re.I,
)
_AR_STRONG = (
    "أعمال البناء", "اعمال البناء", "أعمال الإنشاء", "اعمال الانشاء", "أعمال انشائية",
    "اعمال انشائية", "أعمال مدنية", "اعمال مدنية", "إنشاء مبنى", "انشاء مبنى",
    "إنشاء مباني", "انشاء مباني", "تشييد", "أعمال طرق", "اعمال طرق", "أعمال جسور",
    "اعمال جسور", "ترميم", "إعادة تأهيل مبنى", "اعادة تأهيل مبنى",
)
_DATE_FORMATS = (
    "%d/%m/%Y %I:%M:%S %p",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %I:%M %p",
    "%d/%m/%Y %H:%M",
)


class UAEMoFSourceError(RuntimeError):
    """Transport or publisher-contract error; never reinterpret as zero rows."""


@dataclass(frozen=True)
class FederalOpportunity:
    rfq_number: str
    entity: str
    title: str
    open_date: str
    close_date: str
    detail_url: str | None = None


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[tuple[str, str | None]]] = []
        self._row: list[tuple[str, str | None]] | None = None
        self._cell_parts: list[str] | None = None
        self._cell_href: str | None = None
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
            self._cell_parts = []
            self._cell_href = None
        elif tag == "a" and self._cell_parts is not None:
            for key, value in attrs:
                if key.lower() == "href" and value:
                    self._cell_href = value.strip()

    def handle_data(self, data):
        if not self._skip_depth and self._cell_parts is not None:
            self._cell_parts.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in {"td", "th"} and self._cell_parts is not None and self._row is not None:
            self._row.append((_clean(" ".join(self._cell_parts)), self._cell_href))
            self._cell_parts = None
            self._cell_href = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            self._cell_parts = None
            self._cell_href = None


def _clean(value: str) -> str:
    return _WS.sub(" ", str(value or "")).strip()


def _iso_datetime(value: str) -> str:
    value = _clean(value)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).isoformat(timespec="seconds")
        except ValueError:
            pass
    raise UAEMoFSourceError(f"unrecognized UAE MoF date: {value!r}")


def parse_opportunities(html: str) -> list[FederalOpportunity]:
    if not isinstance(html, str) or not html.strip():
        raise UAEMoFSourceError("empty UAE MoF opportunities HTML")
    if len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise UAEMoFSourceError("UAE MoF response exceeds safety limit")
    if "Current Business Opportunities" not in html or "Open tenders" not in html:
        raise UAEMoFSourceError("UAE MoF opportunity markers missing")

    parser = _TableParser()
    parser.feed(html)
    rows: list[FederalOpportunity] = []
    for cells in parser.rows:
        if len(cells) < 5:
            continue
        rfq = cells[0][0]
        if not _RFQ.match(rfq):
            continue
        entity = cells[1][0]
        title = cells[2][0]
        open_date = cells[3][0]
        close_date = cells[4][0]
        href = cells[5][1] if len(cells) > 5 else None
        if not entity or not title or not open_date or not close_date:
            raise UAEMoFSourceError(f"incomplete UAE MoF row for RFQ {rfq}")
        rows.append(
            FederalOpportunity(
                rfq_number=rfq,
                entity=entity,
                title=title,
                open_date=open_date,
                close_date=close_date,
                detail_url=urljoin(SOURCE_URL, href) if href else None,
            )
        )
    if not rows:
        raise UAEMoFSourceError("UAE MoF source contract changed: no RFQ rows parsed")
    return rows


def is_construction_relevant(opportunity: FederalOpportunity) -> bool:
    title = opportunity.title
    if _EN_STRONG.search(title):
        return True
    return any(term in title for term in _AR_STRONG)


def normalize_opportunity(opportunity: FederalOpportunity) -> dict:
    if not _RFQ.match(opportunity.rfq_number):
        raise UAEMoFSourceError(f"invalid RFQ identity: {opportunity.rfq_number!r}")
    opened = _iso_datetime(opportunity.open_date)
    deadline = _iso_datetime(opportunity.close_date)
    if deadline < opened:
        raise UAEMoFSourceError(f"RFQ {opportunity.rfq_number} close date predates open date")
    return {
        "source": SOURCE,
        "signal_type": "TENDER",
        "external_id": opportunity.rfq_number,
        "source_reference": opportunity.rfq_number,
        "title": opportunity.title,
        "description": None,
        "buyer": opportunity.entity,
        "country": COUNTRY,
        "publication_date": opened[:10],
        "published_at": opened,
        "source_updated_at": None,
        "deadline": deadline,
        "url": opportunity.detail_url or SOURCE_URL,
        "taxonomy": "AE_MOF_DPP_STRONG_TITLE_WORKS_V1",
        "category_code": None,
        "place": "United Arab Emirates",
        "construction_relevant": True,
        "coverage_scope": "LIMITED_HIGH_VALUE_SLICE_UAE_FEDERAL_DPP_PUBLIC_OPPORTUNITIES",
    }


def normalize_construction_opportunities(opportunities: Iterable[FederalOpportunity]) -> list[dict]:
    return [normalize_opportunity(o) for o in opportunities if is_construction_relevant(o)]


def _get_page(client, page: int, *, timeout: float) -> str:
    url = SOURCE_URL if page == 1 else f"{SOURCE_URL}?mof-dpp-page={page}"
    try:
        response = client.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "ObraSignal/1.0 (+official-source-validation)"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise UAEMoFSourceError(f"UAE MoF fetch failed on page {page}: {exc}") from exc
    return response.text


def fetch_current_opportunities(*, session=None, timeout: float = 20.0, max_pages: int = MAX_PAGES) -> list[FederalOpportunity]:
    if not 1 <= int(max_pages) <= MAX_PAGES:
        raise ValueError(f"max_pages must be between 1 and {MAX_PAGES}")
    client = session or requests
    all_rows: dict[str, FederalOpportunity] = {}
    previous_signature: tuple[str, ...] | None = None
    for page in range(1, int(max_pages) + 1):
        rows = parse_opportunities(_get_page(client, page, timeout=timeout))
        signature = tuple(r.rfq_number for r in rows)
        if previous_signature is not None and signature == previous_signature:
            break
        previous_signature = signature
        before = len(all_rows)
        for row in rows:
            existing = all_rows.get(row.rfq_number)
            if existing and existing != row:
                raise UAEMoFSourceError(f"conflicting duplicate RFQ {row.rfq_number} across pages")
            all_rows[row.rfq_number] = row
        if len(all_rows) == before:
            break
    if not all_rows:
        raise UAEMoFSourceError("UAE MoF fetch returned no opportunities")
    return list(all_rows.values())


def fetch_normalized_construction_tenders(*, session=None, timeout: float = 20.0, max_pages: int = MAX_PAGES) -> list[dict]:
    """Return the conservative federal construction slice after a valid observation.

    A valid publisher response can legitimately contain zero RFQs admitted by
    the conservative construction classifier. That is returned as an empty list,
    while transport, schema, parsing, pagination and identity failures continue
    to raise UAEMoFSourceError.
    """
    raw = fetch_current_opportunities(session=session, timeout=timeout, max_pages=max_pages)
    normalized = normalize_construction_opportunities(raw)
    ids = [r["external_id"] for r in normalized]
    if len(ids) != len(set(ids)):
        raise UAEMoFSourceError("duplicate UAE MoF RFQ identity after normalization")
    return normalized


class UAEMoFDPPConnector:
    """Registry-candidate adapter for the bounded federal public opportunity route."""

    source = SOURCE

    def __init__(self, *, session=None, timeout: float = 20.0, max_pages: int = MAX_PAGES):
        self.session = session
        self.timeout = timeout
        self.max_pages = max_pages

    def fetch(self) -> list[dict]:
        return fetch_normalized_construction_tenders(
            session=self.session,
            timeout=self.timeout,
            max_pages=self.max_pages,
        )
