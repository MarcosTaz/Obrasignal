"""Kuwait Central Agency for Public Tenders public-tender connector.

Coverage is a LIMITED HIGH-VALUE SLICE: publicly listed CAPT open tenders,
construction/public-works rows only. Tender documents may require registered
supplier access; this module uses only the public listing and is not runtime-enabled.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
import re
from typing import Iterable

import requests


SOURCE = "KW_CAPT"
SOURCE_URL = "https://capt.gov.kw/ar/tenders/opening-tenders/"
COUNTRY = "KWT"
MAX_HTML_BYTES = 5_000_000
MAX_PAGES = 10

_WS = re.compile(r"\s+")
_LABELS = {
    "الرقم": "tender_no",
    "الجهة": "buyer",
    "الموضوع": "title",
    "تاريخ الطلب": "request_date",
    "اخر موعد للعطاء": "deadline",
    "آخر موعد للعطاء": "deadline",
    "تاريخ الإجتماع التمهيدي": "premeeting_date",
    "تاريخ الاجتماع التمهيدي": "premeeting_date",
}
_MONTHS = {
    "يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4,
    "مايو": 5, "يونيو": 6, "يوليو": 7, "أغسطس": 8, "اغسطس": 8,
    "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12,
}
_AR_STRONG = (
    "اعمال انشائية", "أعمال انشائية", "الاعمال الانشائية", "الأعمال الإنشائية",
    "اعمال مدنية", "أعمال مدنية", "الاعمال المدنية", "الأعمال المدنية",
    "اعمال مدنيه", "أعمال مدنيه", "الاعمال المدنيه", "الأعمال المدنيه",
    "انشاء و انجاز", "إنشاء وإنجاز", "إنشاء و إنجاز", "ترميم المباني",
    "صيانة و ترميم المباني", "صيانة وترميم المباني", "تنفيذ أعمال التشغيل والصيانة",
    "تنفيذ اعمال التشغيل والصيانة", "إنشاء مبنى", "انشاء مبنى", "إنشاء مباني",
    "انشاء مباني", "أعمال الطرق", "اعمال الطرق", "إنشاء طرق", "انشاء طرق",
    "أعمال الجسور", "اعمال الجسور", "مشروع مبنى", "توسعة مبنى",
)
_EN_STRONG = re.compile(
    r"\b(?:construction|civil works|building works|road works|bridge works|renovation|rehabilitation|design and build)\b",
    re.I,
)


class KuwaitCAPTSourceError(RuntimeError):
    """Transport or publisher-contract error; never reinterpret as zero tenders."""


@dataclass(frozen=True)
class CAPTTender:
    tender_no: str
    buyer: str
    title: str
    request_date: str
    deadline: str
    premeeting_date: str | None = None


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = _clean(data)
        if text:
            self.tokens.append(text)


def _clean(value: str) -> str:
    return _WS.sub(" ", str(value or "")).strip()


def _iso_date(value: str, *, allow_blank: bool = False) -> str | None:
    value = _clean(value)
    if not value and allow_blank:
        return None
    match = re.fullmatch(r"([^\s]+)\s+(\d{1,2}),\s*(\d{4})", value)
    if not match:
        raise KuwaitCAPTSourceError(f"unrecognized CAPT date: {value!r}")
    month_name, day, year = match.groups()
    month = _MONTHS.get(month_name)
    if not month:
        raise KuwaitCAPTSourceError(f"unrecognized CAPT month: {month_name!r}")
    try:
        return date(int(year), month, int(day)).isoformat()
    except ValueError as exc:
        raise KuwaitCAPTSourceError(f"invalid CAPT date: {value!r}") from exc


def _next_value(tokens: list[str], start: int) -> tuple[str, int]:
    index = start + 1
    while index < len(tokens):
        value = _clean(tokens[index])
        if value and value not in _LABELS:
            return value, index
        index += 1
    raise KuwaitCAPTSourceError("CAPT field label has no following value")


def parse_open_tenders(html: str) -> list[CAPTTender]:
    if not isinstance(html, str) or not html.strip():
        raise KuwaitCAPTSourceError("empty CAPT HTML")
    if len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise KuwaitCAPTSourceError("CAPT response exceeds safety limit")
    if "المناقصات المطروحة" not in html:
        raise KuwaitCAPTSourceError("CAPT open-tender marker missing")

    parser = _TextParser()
    parser.feed(html)
    tokens = parser.tokens
    rows: list[CAPTTender] = []
    current: dict[str, str] = {}

    for idx, token in enumerate(tokens):
        field = _LABELS.get(token)
        if not field:
            continue
        value, _ = _next_value(tokens, idx)
        if field == "tender_no" and current.get("tender_no"):
            if all(current.get(k) for k in ("tender_no", "buyer", "title", "request_date", "deadline")):
                rows.append(CAPTTender(current["tender_no"], current["buyer"], current["title"], current["request_date"], current["deadline"], current.get("premeeting_date")))
            current = {}
        current[field] = value

    if current.get("tender_no") and all(current.get(k) for k in ("buyer", "title", "request_date", "deadline")):
        rows.append(CAPTTender(current["tender_no"], current["buyer"], current["title"], current["request_date"], current["deadline"], current.get("premeeting_date")))

    unique: dict[str, CAPTTender] = {}
    for row in rows:
        if not row.tender_no or len(row.tender_no) > 100:
            continue
        existing = unique.get(row.tender_no)
        if existing and existing != row:
            raise KuwaitCAPTSourceError(f"conflicting duplicate tender {row.tender_no!r}")
        unique[row.tender_no] = row
    if not unique:
        raise KuwaitCAPTSourceError("CAPT source contract changed: no labelled tenders parsed")
    return list(unique.values())


def is_construction_relevant(tender: CAPTTender) -> bool:
    title = tender.title
    if _EN_STRONG.search(title):
        return True
    return any(term in title for term in _AR_STRONG)


def normalize_tender(tender: CAPTTender) -> dict:
    requested = _iso_date(tender.request_date)
    deadline = _iso_date(tender.deadline)
    premeeting = _iso_date(tender.premeeting_date or "", allow_blank=True)
    if deadline < requested:
        raise KuwaitCAPTSourceError(f"CAPT tender {tender.tender_no!r} deadline predates request date")
    return {
        "source": SOURCE,
        "signal_type": "TENDER",
        "external_id": tender.tender_no,
        "source_reference": tender.tender_no,
        "title": tender.title,
        "description": None,
        "buyer": tender.buyer,
        "country": COUNTRY,
        "publication_date": requested,
        "published_at": None,
        "source_updated_at": None,
        "deadline": deadline,
        "url": SOURCE_URL,
        "taxonomy": "KW_CAPT_STRONG_TITLE_WORKS_V1",
        "category_code": None,
        "place": "Kuwait",
        "construction_relevant": True,
        "premeeting_date": premeeting,
        "coverage_scope": "LIMITED_HIGH_VALUE_SLICE_KW_CAPT_PUBLIC_OPEN_TENDERS",
    }


def normalize_construction_tenders(tenders: Iterable[CAPTTender]) -> list[dict]:
    return [normalize_tender(t) for t in tenders if is_construction_relevant(t)]


def _get_page(client, page: int, *, timeout: float) -> str:
    url = SOURCE_URL if page == 1 else f"{SOURCE_URL}?page={page}"
    try:
        response = client.get(url, timeout=timeout, headers={"User-Agent": "ObraSignal/1.0 (+official-source-validation)"})
        response.raise_for_status()
    except requests.RequestException as exc:
        raise KuwaitCAPTSourceError(f"CAPT fetch failed on page {page}: {exc}") from exc
    return response.text


def fetch_open_tenders(*, session=None, timeout: float = 20.0, max_pages: int = 3) -> list[CAPTTender]:
    if not 1 <= int(max_pages) <= MAX_PAGES:
        raise ValueError(f"max_pages must be between 1 and {MAX_PAGES}")
    client = session or requests
    all_rows: dict[str, CAPTTender] = {}
    previous_signature: tuple[str, ...] | None = None
    for page in range(1, int(max_pages) + 1):
        rows = parse_open_tenders(_get_page(client, page, timeout=timeout))
        signature = tuple(r.tender_no for r in rows)
        if signature == previous_signature:
            break
        previous_signature = signature
        before = len(all_rows)
        for row in rows:
            existing = all_rows.get(row.tender_no)
            if existing and existing != row:
                raise KuwaitCAPTSourceError(f"conflicting duplicate tender {row.tender_no!r} across pages")
            all_rows[row.tender_no] = row
        if len(all_rows) == before:
            break
    if not all_rows:
        raise KuwaitCAPTSourceError("CAPT fetch returned no tenders")
    return list(all_rows.values())


def fetch_normalized_construction_tenders(*, session=None, timeout: float = 20.0, max_pages: int = 3) -> list[dict]:
    rows = fetch_open_tenders(session=session, timeout=timeout, max_pages=max_pages)
    return normalize_construction_tenders(rows)


class KuwaitCAPTConnector:
    """Registry-candidate adapter for the public CAPT open-tender route."""

    source = SOURCE

    def __init__(self, *, session=None, timeout: float = 20.0, max_pages: int = 3):
        self.session = session
        self.timeout = timeout
        self.max_pages = max_pages

    def fetch(self) -> list[dict]:
        return fetch_normalized_construction_tenders(session=self.session, timeout=self.timeout, max_pages=self.max_pages)
