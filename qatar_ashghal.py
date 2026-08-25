"""Bounded official Qatar Ashghal open-tender connector.

Coverage is intentionally a LIMITED HIGH-VALUE SLICE: Public Works Authority
(Ashghal) open e-tenders only. It is not national Qatar procurement coverage and
it is not runtime-enabled by this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
import re
from typing import Iterable

import requests


SOURCE = "QA_ASHGHAL"
SOURCE_URL = "https://www.ashghal.gov.qa/en/Tenders/pages/ERPTenderDetailes.aspx?Status=Open"
BUYER = "Public Works Authority (Ashghal)"
COUNTRY = "QAT"
MAX_HTML_BYTES = 5_000_000
MAX_TIMEOUT_SECONDS = 60.0

# Deliberately conservative construction/public-works vocabulary. The source is
# itself a public-works authority, but IT/insurance/events rows still occur and
# must not leak into the construction radar merely because of the publisher.
_CONSTRUCTION_TERMS = (
    "road", "roads", "infrastructure", "drainage", "stormwater", "sewer",
    "building", "buildings", "construction", "civil", "renovation",
    "rehabilitation", "upgrade", "bridge", "tunnel", "pavement", "landscape",
    "excavation", "maintenance works", "design and build", "d&b",
    "supervision consultancy", "engineering consultancy", "survey works",
)
_CONSTRUCTION_PATTERNS = tuple(
    re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.I)
    for term in _CONSTRUCTION_TERMS
)

_DATE_FORMATS = ("%d %B %Y", "%d %b %Y")
_TENDER_REF = re.compile(r"^PWA/[A-Z]+/[A-Z0-9-]+/[0-9]{4}(?:/[A-Z0-9]+)*$", re.I)
_WS = re.compile(r"\s+")


class AshghalSourceError(RuntimeError):
    """Transport or publisher-contract failure. Never reinterpret as zero rows."""


@dataclass(frozen=True)
class AshghalTender:
    tender_no: str
    tender_type: str
    title: str
    issuing_date: str
    closing_date: str
    category: str = ""


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            text = _WS.sub(" ", "".join(self._cell)).strip()
            self._row.append(text)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            self._cell = None


def _iso_date(value: str) -> str:
    value = _WS.sub(" ", str(value or "")).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    raise AshghalSourceError(f"unrecognized Ashghal date: {value!r}")


def parse_open_tenders(html: str) -> list[AshghalTender]:
    if not isinstance(html, str) or not html.strip():
        raise AshghalSourceError("empty Ashghal HTML")
    if len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise AshghalSourceError("Ashghal HTML exceeds safety limit")
    parser = _TableParser()
    parser.feed(html)
    rows: list[AshghalTender] = []
    for cells in parser.rows:
        if len(cells) < 5:
            continue
        tender_no = cells[0].strip()
        if not _TENDER_REF.match(tender_no):
            continue
        rows.append(
            AshghalTender(
                tender_no=tender_no,
                tender_type=cells[1].strip(),
                title=cells[2].strip(),
                issuing_date=cells[3].strip(),
                closing_date=cells[4].strip(),
                category=cells[5].strip() if len(cells) > 5 else "",
            )
        )
    if not rows:
        raise AshghalSourceError("Ashghal source contract changed: no tender rows parsed")
    return rows


def is_construction_relevant(tender: AshghalTender) -> bool:
    haystack = f"{tender.title} {tender.category}"
    return any(pattern.search(haystack) for pattern in _CONSTRUCTION_PATTERNS)


def normalize_tender(tender: AshghalTender) -> dict:
    if not _TENDER_REF.match(tender.tender_no):
        raise AshghalSourceError(f"invalid publisher tender identity: {tender.tender_no!r}")
    if not tender.title.strip():
        raise AshghalSourceError("Ashghal tender title is required")
    publication_date = _iso_date(tender.issuing_date)
    deadline = _iso_date(tender.closing_date)
    if deadline < publication_date:
        raise AshghalSourceError(
            f"Ashghal closing date precedes issuing date for {tender.tender_no}"
        )
    return {
        "source": SOURCE,
        "signal_type": "TENDER",
        "external_id": tender.tender_no,
        "source_reference": tender.tender_no,
        "title": tender.title,
        "description": None,
        "buyer": BUYER,
        "country": COUNTRY,
        "publication_date": publication_date,
        "published_at": None,
        "source_updated_at": None,
        "deadline": deadline,
        "url": SOURCE_URL,
        "taxonomy": "ASHGHAL_TITLE_KEYWORDS_V1",
        "category_code": tender.tender_type or None,
        "place": "Qatar",
        "construction_relevant": True,
        "coverage_scope": "LIMITED_HIGH_VALUE_SLICE_ASHGHAL_OPEN_ETENDERS",
    }


def normalize_construction_tenders(tenders: Iterable[AshghalTender]) -> list[dict]:
    return [normalize_tender(t) for t in tenders if is_construction_relevant(t)]


def fetch_open_tenders(*, session=None, timeout: float = 20.0) -> list[AshghalTender]:
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not (0 < timeout <= MAX_TIMEOUT_SECONDS):
        raise ValueError(f"timeout must be > 0 and <= {MAX_TIMEOUT_SECONDS:g} seconds")
    client = session or requests
    try:
        response = client.get(
            SOURCE_URL,
            timeout=timeout,
            headers={"User-Agent": "ObraSignal/1.0 (+official-source-validation)"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise AshghalSourceError(f"Ashghal fetch failed: {exc}") from exc
    html = response.text
    if "Open Tenders" not in html and "Open e-Tenders" not in html:
        raise AshghalSourceError("Ashghal open-tender marker missing")
    return parse_open_tenders(html)


def fetch_normalized_construction_tenders(*, session=None, timeout: float = 20.0) -> list[dict]:
    raw = fetch_open_tenders(session=session, timeout=timeout)
    normalized = normalize_construction_tenders(raw)
    if not normalized:
        raise AshghalSourceError(
            "Ashghal fetch succeeded but construction classifier admitted zero records"
        )
    identities = [r["external_id"] for r in normalized]
    if len(identities) != len(set(identities)):
        raise AshghalSourceError("duplicate Ashghal tender identity in one fetch")
    return normalized


class AshghalOpenTenderConnector:
    """Thin source adapter named by the canonical registry.

    The class exposes the tested fetch/normalize path without opting the source
    into any runtime. Callers must still honor ``source_registry`` production
    gates before commercial ingestion.
    """

    source = SOURCE

    def __init__(self, *, session=None, timeout: float = 20.0):
        self.session = session
        self.timeout = timeout

    def fetch(self) -> list[dict]:
        return fetch_normalized_construction_tenders(
            session=self.session,
            timeout=self.timeout,
        )
