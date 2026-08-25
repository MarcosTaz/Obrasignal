"""Morocco public procurement portal construction-category connector.

Coverage is a LIMITED HIGH-VALUE SLICE: the first current-results page returned
by the official `Travaux de construction et d'aménagement` category search.
The publisher uses JavaScript/WebForms-style postback pagination; v0 detects and
records that pagination surface but deliberately does not emulate it. This is
not every PMMP category/page/lifecycle surface and it is not runtime-enabled.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
import re
from typing import Iterable

import requests

SOURCE = "MA_PMMP"
SOURCE_URL = "https://www.marchespublics.gov.ma/index.php?AllCons=&EnCours=&domaineActivite=1.15&page=entreprise.EntrepriseAdvancedSearch"
COUNTRY = "MAR"
MAX_HTML_BYTES = 6_000_000

_WS = re.compile(r"\s+")
_DATE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
_REF = re.compile(r"^\s*(.+?)\s+-\s+(?:\.\.\.\s*)?Objet\s*:", re.I)
_TITLE = re.compile(r"Objet\s*:\s*(.*?)(?:\s+\.\.\.\s+|\s+Acheteur public\s*:)", re.I)
_BUYER = re.compile(r"Acheteur public\s*:\s*(.+)$", re.I)
_DEADLINE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2})\b")


class MoroccoPMMPSourceError(RuntimeError):
    """Transport or publisher-contract error; never reinterpret as zero rows."""


@dataclass(frozen=True)
class PMMPConsultation:
    reference: str
    title: str
    buyer: str
    published: str
    deadline: str
    procedure: str
    location: str = ""


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None
        self._skip_depth = 0
        self._anchor_href: str | None = None
        self.next_href: str | None = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell_parts = []
        elif tag == "a":
            self._anchor_href = attrs.get("href")
            label = _clean(attrs.get("title") or "")
            if "page suivante" in label.casefold() and self._anchor_href:
                self.next_href = self._anchor_href
        elif tag == "img" and self._anchor_href:
            alt = _clean(attrs.get("alt") or "")
            title = _clean(attrs.get("title") or "")
            if "page suivante" in f"{alt} {title}".casefold():
                self.next_href = self._anchor_href

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in {"td", "th"} and self._cell_parts is not None and self._row is not None:
            self._row.append(_clean(" ".join(self._cell_parts)))
            self._cell_parts = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            self._cell_parts = None
        elif tag == "a":
            self._anchor_href = None

    def handle_data(self, data):
        if not self._skip_depth and self._cell_parts is not None:
            self._cell_parts.append(data)


def _clean(value: str) -> str:
    return _WS.sub(" ", str(value or "")).strip()


def _iso_date(value: str) -> str:
    try:
        return datetime.strptime(_clean(value), "%d/%m/%Y").date().isoformat()
    except ValueError as exc:
        raise MoroccoPMMPSourceError(f"unrecognized PMMP date: {value!r}") from exc


def _iso_deadline(value: str) -> str:
    match = _DEADLINE.search(_clean(value))
    if not match:
        raise MoroccoPMMPSourceError(f"unrecognized PMMP deadline: {value!r}")
    try:
        return datetime.strptime(f"{match.group(1)} {match.group(2)}", "%d/%m/%Y %H:%M").isoformat(timespec="minutes")
    except ValueError as exc:
        raise MoroccoPMMPSourceError(f"invalid PMMP deadline: {value!r}") from exc


def parse_consultations_page(html: str) -> tuple[list[PMMPConsultation], str | None]:
    if not isinstance(html, str) or not html.strip():
        raise MoroccoPMMPSourceError("empty PMMP HTML")
    if len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise MoroccoPMMPSourceError("PMMP response exceeds safety limit")
    if "Résultats de la recherche" not in html or "Travaux" not in html:
        raise MoroccoPMMPSourceError("PMMP construction-search markers missing")

    parser = _PageParser()
    parser.feed(html)
    results: list[PMMPConsultation] = []

    for cells in parser.rows:
        details_cell = next((cell for cell in cells if "Objet" in cell and "Acheteur public" in cell), None)
        procedure_cell = next((cell for cell in cells if "Travaux" in cell and _DATE.search(cell)), None)
        deadline_cell = next((cell for cell in cells if _DEADLINE.search(cell)), None)
        if not details_cell or not procedure_cell or not deadline_cell:
            continue
        ref_match = _REF.search(details_cell)
        title_match = _TITLE.search(details_cell)
        buyer_match = _BUYER.search(details_cell)
        published_match = _DATE.search(procedure_cell)
        if not (ref_match and title_match and buyer_match and published_match):
            continue
        reference = _clean(ref_match.group(1))
        title = _clean(title_match.group(1)).strip(" .")
        buyer = _clean(buyer_match.group(1)).strip(" .").split(" | ")[0].strip()
        procedure = "AOS" if "Appel d'offres ouvert simplifié" in procedure_cell else "AOO" if "Appel d'offres ouvert" in procedure_cell else "Travaux"
        deadline_match = _DEADLINE.search(deadline_cell)
        deadline = f"{deadline_match.group(1)} {deadline_match.group(2)}"
        location = ""
        for cell in cells:
            if cell in {details_cell, procedure_cell, deadline_cell}:
                continue
            candidate = _clean(cell).strip(" .-")
            if 2 < len(candidate) < 100 and candidate.upper() == candidate and any(ch.isalpha() for ch in candidate):
                location = candidate
                break
        if reference and title and buyer:
            results.append(PMMPConsultation(reference, title, buyer, published_match.group(1), deadline, procedure, location))

    unique: dict[str, PMMPConsultation] = {}
    for row in results:
        identity = f"{row.buyer}::{row.reference}"
        existing = unique.get(identity)
        if existing and existing != row:
            raise MoroccoPMMPSourceError(f"conflicting PMMP duplicate {identity!r}")
        unique[identity] = row
    if not unique:
        raise MoroccoPMMPSourceError("PMMP source contract changed: no construction consultations parsed")
    return list(unique.values()), parser.next_href


def pagination_state(next_href: str | None) -> str:
    """Describe the publisher pagination contract without pretending to follow it."""
    if not next_href:
        return "NONE"
    if next_href.strip().lower().startswith("javascript:"):
        return "WEBFORMS_POSTBACK_UNIMPLEMENTED_V0"
    return "UNEXPECTED_LINK_PAGINATION"


def normalize_consultation(row: PMMPConsultation) -> dict:
    published = _iso_date(row.published)
    deadline = _iso_deadline(row.deadline)
    if deadline[:10] < published:
        raise MoroccoPMMPSourceError(f"PMMP {row.reference!r} deadline predates publication")
    external_id = f"{row.buyer}::{row.reference}"
    return {
        "source": SOURCE,
        "signal_type": "TENDER",
        "external_id": external_id,
        "source_reference": row.reference,
        "title": row.title,
        "description": None,
        "buyer": row.buyer,
        "country": COUNTRY,
        "publication_date": published,
        "published_at": None,
        "source_updated_at": None,
        "deadline": deadline,
        "url": SOURCE_URL,
        "taxonomy": "MA_PMMP_OFFICIAL_TRAVAUX_CONSTRUCTION_AMENAGEMENT_V1",
        "category_code": "Travaux / construction et amenagement",
        "place": row.location or "Morocco",
        "construction_relevant": True,
        "procedure": row.procedure,
        "coverage_scope": "LIMITED_HIGH_VALUE_SLICE_MA_PMMP_CONSTRUCTION_AMENAGEMENT_PAGE1",
    }


def normalize_consultations(rows: Iterable[PMMPConsultation]) -> list[dict]:
    return [normalize_consultation(row) for row in rows]


def _get(client, url: str, *, timeout: float) -> str:
    try:
        response = client.get(url, timeout=timeout, headers={"User-Agent": "ObraSignal/1.0 (+official-source-validation)"})
        response.raise_for_status()
    except requests.RequestException as exc:
        raise MoroccoPMMPSourceError(f"PMMP fetch failed: {exc}") from exc
    return response.text


def fetch_current_construction_consultations(*, session=None, timeout: float = 25.0) -> list[PMMPConsultation]:
    """Fetch the public first page only; pagination is explicitly not emulated in v0."""
    client = session or requests
    rows, _next_href = parse_consultations_page(_get(client, SOURCE_URL, timeout=timeout))
    return rows


def fetch_normalized_construction_tenders(*, session=None, timeout: float = 25.0) -> list[dict]:
    return normalize_consultations(fetch_current_construction_consultations(session=session, timeout=timeout))


class MoroccoPMMPConnector:
    """Registry-candidate adapter for the official page-1 construction slice."""

    source = SOURCE

    def __init__(self, *, session=None, timeout: float = 25.0):
        self.session = session
        self.timeout = timeout

    def fetch(self) -> list[dict]:
        return fetch_normalized_construction_tenders(session=self.session, timeout=self.timeout)
