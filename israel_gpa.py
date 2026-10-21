"""Bounded Israel Government Procurement Administration public-tender connector.

Coverage is intentionally a LIMITED HIGH-VALUE SLICE: recent notices exposed by
mr.gov.il's public government-procurement search, enriched from public detail
pages, and conservatively filtered for construction/public-works relevance.
This is not every Israeli public buyer and it is not runtime-enabled here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
import re
from typing import Iterable

import requests


SOURCE = "IL_GPA"
SEARCH_URL = "https://mr.gov.il/ilgstorefront/en/search/?s=TENDER"
DETAIL_URL = "https://mr.gov.il/ilgstorefront/en/p/{serial}"
COUNTRY = "ISR"
MAX_HTML_BYTES = 5_000_000
MAX_DETAIL_FETCHES = 25

_DETAIL_HREF = re.compile(r"/ilgstorefront/(?:en|he)/p/(\d{6,})/?(?:[?#].*)?$", re.I)
_SERIAL = re.compile(r"^\d{6,}$")
_WS = re.compile(r"\s+")
_EN_CONSTRUCTION = re.compile(
    r"\b(?:construction|infrastructure|roads?|bridges?|architecture|architectural|renovation|building works|civil works)\b",
    re.I,
)
# Strong physical-works terms only. Generic establishment, water/sewer,
# drainage and isolated "structure/building" wording were observed in
# consulting/organizational notices and are excluded.
_HE_CONSTRUCTION_TERMS = (
    "בנייה", "בניה", "תשתיות", "כביש", "כבישים", "גשר", "גשרים",
    "שיפוץ", "שיפוצים", "אדריכלות", "עבודות בנייה", "עבודות בניה",
    "עבודות תשתית", "עבודות שיפוץ",
)

_NOTICE_TYPES = {"Public Tender", "Central Tender"}
_LABELS = {
    "Publisher:": "publisher",
    "Serial:": "serial",
    "Status:": "status",
    "Process:": "process",
    "Published:": "published",
    "Updated:": "updated",
    "Deadline:": "deadline",
}
_STOP_SUBJECTS = {"About us", "Freedom of info", "Registration", "Contact us", "accessibility"}


class IsraelGPASourceError(RuntimeError):
    """Transport or publisher-contract failure; never reinterpret as zero rows."""


@dataclass(frozen=True)
class GPANotice:
    notice_type: str
    title: str
    publisher: str
    serial: str
    process: str
    status: str
    published: str
    updated: str
    deadline: str
    subjects: tuple[str, ...] = ()


class _HTMLTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens: list[str] = []
        self.headings: list[tuple[str, str]] = []
        self.links: list[str] = []
        self._skip_depth = 0
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in {"h1", "h2", "h3", "h4"}:
            self._heading_tag = tag
            self._heading_parts = []
        if tag == "a":
            for key, value in attrs:
                if key.lower() == "href" and value:
                    self.links.append(value.strip())

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if self._heading_tag == tag:
            text = _clean(" ".join(self._heading_parts))
            if text:
                self.headings.append((tag, text))
            self._heading_tag = None
            self._heading_parts = []

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = _clean(data)
        if not text:
            return
        self.tokens.append(text)
        if self._heading_tag:
            self._heading_parts.append(text)


def _clean(value: str) -> str:
    return _WS.sub(" ", str(value or "")).strip()


def _parse_date(value: str, *, allow_blank: bool = False) -> str | None:
    value = _clean(value).replace(" ,", " ").replace(",", " ")
    if not value and allow_blank:
        return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).isoformat(timespec="minutes") if "%H" in fmt else datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    raise IsraelGPASourceError(f"unrecognized GPA date: {value!r}")


def parse_search_serials(html: str, *, limit: int = MAX_DETAIL_FETCHES) -> list[str]:
    if not isinstance(html, str) or not html.strip():
        raise IsraelGPASourceError("empty GPA search HTML")
    if len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise IsraelGPASourceError("GPA search HTML exceeds safety limit")
    parser = _HTMLTextParser()
    parser.feed(html)
    serials: list[str] = []
    seen: set[str] = set()
    for href in parser.links:
        match = _DETAIL_HREF.search(href)
        if not match:
            continue
        serial = match.group(1)
        if serial not in seen:
            seen.add(serial)
            serials.append(serial)
        if len(serials) >= int(limit):
            break
    if not serials:
        raise IsraelGPASourceError("GPA source contract changed: no detail links found")
    return serials


def _value_after(tokens: list[str], label: str) -> str:
    try:
        idx = tokens.index(label)
    except ValueError as exc:
        raise IsraelGPASourceError(f"GPA detail missing {label}") from exc
    if idx + 1 >= len(tokens):
        raise IsraelGPASourceError(f"GPA detail missing value after {label}")
    return _clean(tokens[idx + 1])


def parse_detail(html: str) -> GPANotice:
    if not isinstance(html, str) or not html.strip():
        raise IsraelGPASourceError("empty GPA detail HTML")
    if len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise IsraelGPASourceError("GPA detail HTML exceeds safety limit")
    parser = _HTMLTextParser()
    parser.feed(html)

    h1 = [text for tag, text in parser.headings if tag == "h1"]
    h2 = [text for tag, text in parser.headings if tag == "h2"]
    if not h1 or not h2:
        raise IsraelGPASourceError("GPA detail heading contract changed")
    notice_type = h1[0]
    title = h2[0]

    values = {key: _value_after(parser.tokens, label) for label, key in _LABELS.items()}
    if not _SERIAL.match(values["serial"]):
        raise IsraelGPASourceError(f"invalid GPA serial: {values['serial']!r}")

    subjects: list[str] = []
    try:
        start = parser.tokens.index("Subjects") + 1
    except ValueError:
        start = len(parser.tokens)
    for token in parser.tokens[start:]:
        if token in _STOP_SUBJECTS:
            break
        if token and token not in subjects:
            subjects.append(token)

    return GPANotice(
        notice_type=notice_type,
        title=title,
        publisher=values["publisher"],
        serial=values["serial"],
        process=values["process"],
        status=values["status"],
        published=values["published"],
        updated=values["updated"],
        deadline=values["deadline"],
        subjects=tuple(subjects),
    )


def is_construction_relevant(notice: GPANotice) -> bool:
    """Fail closed on strong physical-works evidence in the publisher title.

    Subjects remain metadata only because the live portal can expose broad or
    hidden taxonomy values. Ambiguous title terms observed in consulting notices
    are excluded. Precision is intentionally favored over recall in v0.
    """
    title = _clean(notice.title)
    if _EN_CONSTRUCTION.search(title):
        return True
    return any(term in title for term in _HE_CONSTRUCTION_TERMS)


def normalize_notice(notice: GPANotice) -> dict:
    if notice.notice_type not in _NOTICE_TYPES:
        raise IsraelGPASourceError(f"unsupported GPA notice type for v0: {notice.notice_type!r}")
    if not _SERIAL.match(notice.serial):
        raise IsraelGPASourceError(f"invalid GPA serial: {notice.serial!r}")
    published = _parse_date(notice.published)
    updated = _parse_date(notice.updated)
    deadline = _parse_date(notice.deadline, allow_blank=True)
    if deadline and deadline[:10] < published[:10]:
        raise IsraelGPASourceError("GPA deadline predates publication")
    return {
        "source": SOURCE,
        "signal_type": "TENDER",
        "external_id": notice.serial,
        "source_reference": notice.serial,
        "title": notice.title,
        "description": None,
        "buyer": notice.publisher,
        "country": COUNTRY,
        "publication_date": published[:10],
        "published_at": None,
        "source_updated_at": updated,
        "deadline": deadline,
        "url": DETAIL_URL.format(serial=notice.serial),
        "taxonomy": "IL_GPA_STRONG_TITLE_WORKS_V1",
        "category_code": notice.notice_type,
        "place": "Israel",
        "construction_relevant": True,
        "process_reference": notice.process or None,
        "publisher_status": notice.status or None,
        "subjects": list(notice.subjects),
        "coverage_scope": "LIMITED_HIGH_VALUE_SLICE_IL_GPA_RECENT_PUBLIC_TENDERS",
    }


def normalize_construction_notices(notices: Iterable[GPANotice]) -> list[dict]:
    return [normalize_notice(n) for n in notices if n.notice_type in _NOTICE_TYPES and is_construction_relevant(n)]


def _get_text(client, url: str, *, timeout: float) -> str:
    try:
        response = client.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "ObraSignal/1.0 (+official-source-validation)"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise IsraelGPASourceError(f"GPA fetch failed: {exc}") from exc
    text = response.text
    if len(text.encode("utf-8")) > MAX_HTML_BYTES:
        raise IsraelGPASourceError("GPA response exceeds safety limit")
    return text


def fetch_recent_notices(*, session=None, timeout: float = 20.0, max_details: int = MAX_DETAIL_FETCHES) -> list[GPANotice]:
    client = session or requests
    if not 1 <= int(max_details) <= MAX_DETAIL_FETCHES:
        raise ValueError(f"max_details must be between 1 and {MAX_DETAIL_FETCHES}")
    search_html = _get_text(client, SEARCH_URL, timeout=timeout)
    serials = parse_search_serials(search_html, limit=max_details)
    notices = []
    for serial in serials:
        notice = parse_detail(_get_text(client, DETAIL_URL.format(serial=serial), timeout=timeout))
        if notice.serial != serial:
            raise IsraelGPASourceError(f"GPA identity mismatch: link {serial}, detail {notice.serial}")
        notices.append(notice)
    return notices


def fetch_normalized_construction_tenders(*, session=None, timeout: float = 20.0, max_details: int = MAX_DETAIL_FETCHES) -> list[dict]:
    notices = fetch_recent_notices(session=session, timeout=timeout, max_details=max_details)
    normalized = normalize_construction_notices(notices)
    if not normalized:
        raise IsraelGPASourceError("GPA fetch succeeded but construction classifier admitted zero records")
    ids = [r["external_id"] for r in normalized]
    if len(ids) != len(set(ids)):
        raise IsraelGPASourceError("duplicate GPA publisher identity in one fetch")
    return normalized


class IsraelGPAConnector:
    """Registry-candidate adapter for the bounded public-search/detail route."""

    source = SOURCE

    def __init__(self, *, session=None, timeout: float = 20.0, max_details: int = MAX_DETAIL_FETCHES):
        self.session = session
        self.timeout = timeout
        self.max_details = max_details

    def fetch(self) -> list[dict]:
        return fetch_normalized_construction_tenders(
            session=self.session,
            timeout=self.timeout,
            max_details=self.max_details,
        )
