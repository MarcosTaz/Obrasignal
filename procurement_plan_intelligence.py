"""Canonical procurement-plan intelligence for formal pre-tender signals.

This capability is deliberately read/normalization oriented. It consumes normalized
Signal records and never promotes a plan/forecast/PIN into a live tender. Partial
source dates remain partial: derived ranges are explicitly marked as derived.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from typing import Mapping

PLAN_SIGNAL_TYPES = frozenset({"PROCUREMENT_PLAN", "FORECAST", "PRIOR_INFORMATION", "CAPITAL_PROJECT", "MARKET_DIALOGUE"})
ACTIVE_STATUSES = frozenset({"PLANNED", "PUBLISHED", "UPDATED", "UNKNOWN"})
PLAN_STATUSES = frozenset({"PLANNED", "PUBLISHED", "UPDATED", "DEFERRED", "CANCELLED", "SUPERSEDED", "UNKNOWN"})
DATE_PRECISIONS = frozenset({"EXACT", "MONTH", "QUARTER", "YEAR", "RANGE", "WINDOW", "UNKNOWN"})
CONFIDENCE_LEVELS = frozenset({"HIGH", "MEDIUM", "LOW", "UNKNOWN"})
BUDGET_STATUSES = frozenset({"PLANNED", "APPROVED", "ALLOCATED", "INDICATIVE", "UNKNOWN"})
MAX_TITLE = 500
MAX_DESCRIPTION = 50_000
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_QUARTER = re.compile(r"^Q([1-4])\s*[-_/ ]?\s*(\d{4})$", re.I)
_MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
_YEAR = re.compile(r"^(\d{4})$")


def _text(value, limit=None):
    text = "" if value is None else " ".join(str(value).split())
    if limit is not None and len(text) > limit:
        raise ValueError(f"text exceeds {limit} characters")
    return text


def _iso_date(value):
    if not value:
        return None
    text = _text(value)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid exact date: {text}") from exc


def _iso_datetime(value):
    if not value:
        return None
    text = _text(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid timestamp: {text}") from exc


@dataclass(frozen=True)
class PartialDate:
    precision: str
    raw: str = ""
    exact_date: date | None = None
    year: int | None = None
    month: int | None = None
    quarter: int | None = None
    range_start: date | None = None
    range_end: date | None = None
    derived_range: bool = False

    def __post_init__(self):
        if self.precision not in DATE_PRECISIONS:
            raise ValueError("unsupported date precision")
        if self.precision == "EXACT" and self.exact_date is None:
            raise ValueError("EXACT requires exact_date")
        if self.precision == "MONTH" and not (self.year and self.month):
            raise ValueError("MONTH requires year and month")
        if self.precision == "QUARTER" and not (self.year and self.quarter in (1, 2, 3, 4)):
            raise ValueError("QUARTER requires year and quarter")
        if self.precision == "YEAR" and not self.year:
            raise ValueError("YEAR requires year")
        if self.precision == "RANGE" and not (self.range_start and self.range_end and self.range_start <= self.range_end):
            raise ValueError("RANGE requires ordered start/end")

    @property
    def is_exact(self):
        return self.precision == "EXACT"


def parse_partial_date(value=None, *, precision=None, year=None, month=None, quarter=None, start=None, end=None):
    """Parse date semantics without manufacturing an official exact date."""
    if precision:
        p = _text(precision).upper()
        if p == "UNKNOWN":
            return PartialDate("UNKNOWN", raw=_text(value))
        if p == "WINDOW":
            return PartialDate("WINDOW", raw=_text(value))
        if p == "EXACT":
            d = _iso_date(value)
            return PartialDate("EXACT", raw=_text(value), exact_date=d, year=d.year, month=d.month)
        if p == "MONTH":
            return PartialDate("MONTH", raw=_text(value), year=int(year), month=int(month))
        if p == "QUARTER":
            return PartialDate("QUARTER", raw=_text(value), year=int(year), quarter=int(quarter))
        if p == "YEAR":
            return PartialDate("YEAR", raw=_text(value), year=int(year))
        if p == "RANGE":
            return PartialDate("RANGE", raw=_text(value), range_start=_iso_date(start), range_end=_iso_date(end))
        raise ValueError("unsupported date precision")
    text = _text(value)
    if not text:
        return PartialDate("UNKNOWN")
    try:
        d = date.fromisoformat(text)
        return PartialDate("EXACT", raw=text, exact_date=d, year=d.year, month=d.month)
    except ValueError:
        pass
    match = _MONTH.fullmatch(text)
    if match:
        return PartialDate("MONTH", raw=text, year=int(match.group(1)), month=int(match.group(2)))
    match = _QUARTER.fullmatch(text)
    if match:
        return PartialDate("QUARTER", raw=text, year=int(match.group(2)), quarter=int(match.group(1)))
    match = _YEAR.fullmatch(text)
    if match:
        return PartialDate("YEAR", raw=text, year=int(match.group(1)))
    return PartialDate("WINDOW", raw=text)


@dataclass(frozen=True)
class EstimatedValue:
    currency: str | None = None
    estimate: Decimal | None = None
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    semantics: str = "ESTIMATED"

    def __post_init__(self):
        if self.currency and not _CURRENCY.fullmatch(self.currency):
            raise ValueError("currency must be a 3-letter ISO-style code")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("value range minimum exceeds maximum")
        for value in (self.estimate, self.minimum, self.maximum):
            if value is not None and value < 0:
                raise ValueError("planned value cannot be negative")
        if self.semantics != "ESTIMATED":
            raise ValueError("plan value semantics must remain ESTIMATED")


def _decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid estimated value") from exc


def normalize_estimated_value(record):
    currency = _text(record.get("currency")).upper() or None
    return EstimatedValue(
        currency=currency,
        estimate=_decimal(record.get("estimated_value", record.get("value"))),
        minimum=_decimal(record.get("estimated_value_min")),
        maximum=_decimal(record.get("estimated_value_max")),
    )


@dataclass(frozen=True)
class ProcurementPlanSignal:
    signal_id: str
    source_id: str
    native_id: str
    signal_type: str
    title: str
    description: str
    buyer_id: str | None
    buyer_name: str | None
    category: str | None
    location: Mapping | None
    planned_procurement_date: PartialDate
    planned_start_date: PartialDate
    planned_end_date: PartialDate
    expected_tender_date: PartialDate
    budget_year: int | None
    estimated_value: EstimatedValue
    budget_status: str
    procedure_type: str | None
    plan_status: str
    published_at: datetime | None
    source_updated_at: datetime | None
    source_ref: str | None
    confidence: str
    provenance: Mapping
    lineage_ref: str | None
    normalizer_version: str
    revision: str | None
    fingerprint: str
    is_open_tender: bool = False
    is_active_future_procurement: bool = True
    raw: Mapping = field(default_factory=dict, repr=False, compare=False)


def _status(record):
    raw = _text(record.get("plan_status") or record.get("status") or "UNKNOWN").upper()
    aliases = {"ACTIVE": "PLANNED", "PENDING": "PLANNED", "DEFERRED": "DEFERRED", "CANCELED": "CANCELLED"}
    value = aliases.get(raw, raw)
    if record.get("plan_cancelled") is True:
        value = "CANCELLED"
    return value if value in PLAN_STATUSES else "UNKNOWN"


def _budget_status(record):
    value = _text(record.get("budget_status") or "UNKNOWN").upper()
    return value if value in BUDGET_STATUSES else "UNKNOWN"


def _confidence(record, planned):
    explicit = _text(record.get("confidence")).upper()
    if explicit in CONFIDENCE_LEVELS:
        return explicit
    official_id = bool(_text(record.get("source_reference") or record.get("plan_control_id") or record.get("ocid")))
    official = record.get("official_source") is not False
    has_value = any(record.get(key) not in (None, "") for key in ("estimated_value", "value", "estimated_value_min", "estimated_value_max"))
    if official and official_id and planned.precision == "EXACT" and has_value:
        return "HIGH"
    if official and official_id and planned.precision not in ("UNKNOWN",):
        return "MEDIUM"
    if official_id or planned.precision not in ("UNKNOWN",):
        return "LOW"
    return "UNKNOWN"


def _date_from_record(record, key):
    raw = record.get(key)
    prefix = key.removesuffix("_date")
    precision = record.get(f"{prefix}_precision")
    if precision:
        return parse_partial_date(
            raw,
            precision=precision,
            year=record.get(f"{prefix}_year"),
            month=record.get(f"{prefix}_month"),
            quarter=record.get(f"{prefix}_quarter"),
            start=record.get(f"{prefix}_start"),
            end=record.get(f"{prefix}_end"),
        )
    return parse_partial_date(raw)


def normalize_procurement_plan(record: Mapping, *, normalizer_version="procurement-plan-v0") -> ProcurementPlanSignal:
    if not isinstance(record, Mapping):
        raise ValueError("plan record must be a mapping")
    signal_type = _text(record.get("signal_type")).upper()
    if signal_type not in PLAN_SIGNAL_TYPES:
        raise ValueError("record is not a supported pre-tender plan signal")
    source = _text(record.get("source"), 200)
    native_id = _text(record.get("external_id"), 500)
    if not source or not native_id:
        raise ValueError("source and external_id are required")
    title = _text(record.get("title"), MAX_TITLE)
    description = _text(record.get("description"), MAX_DESCRIPTION)
    planned = _date_from_record(record, "planned_procurement_date")
    if planned.precision == "UNKNOWN":
        # Legacy Signal contract uses target_date for future need, not deadline.
        planned = parse_partial_date(record.get("target_date") or record.get("data_desejada"))
    status = _status(record)
    identity = f"{source}:{signal_type}:{native_id}"
    canonical = {str(k): v for k, v in record.items() if not str(k).startswith("_")}
    fingerprint = sha256(json.dumps(canonical, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()
    location = record.get("location") if isinstance(record.get("location"), Mapping) else None
    if location is None and record.get("place"):
        location = {"kind": _text(record.get("location_kind") or "UNKNOWN").upper(), "label": _text(record.get("place"), 1000)}
    budget_year = record.get("budget_year") or record.get("plan_year")
    try:
        budget_year = int(budget_year) if budget_year not in (None, "") else None
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid budget year") from exc
    return ProcurementPlanSignal(
        signal_id=identity,
        source_id=source,
        native_id=native_id,
        signal_type=signal_type,
        title=title,
        description=description,
        buyer_id=_text(record.get("buyer_id")) or None,
        buyer_name=_text(record.get("buyer")) or None,
        category=_text(record.get("category") or record.get("category_code")) or None,
        location=location,
        planned_procurement_date=planned,
        planned_start_date=_date_from_record(record, "planned_start_date"),
        planned_end_date=_date_from_record(record, "planned_end_date"),
        expected_tender_date=_date_from_record(record, "expected_tender_date"),
        budget_year=budget_year,
        estimated_value=normalize_estimated_value(record),
        budget_status=_budget_status(record),
        procedure_type=_text(record.get("procedure_type") or record.get("procurement_method")) or None,
        plan_status=status,
        published_at=_iso_datetime(record.get("published_at")),
        source_updated_at=_iso_datetime(record.get("source_updated_at")),
        source_ref=_text(record.get("source_reference")) or None,
        confidence=_confidence(record, planned),
        provenance={"source": source, "url": _text(record.get("url")) or None, "source_reference": _text(record.get("source_reference")) or None},
        lineage_ref=_text(record.get("lineage_ref")) or None,
        normalizer_version=normalizer_version,
        revision=_text(record.get("revision")) or None,
        fingerprint=fingerprint,
        is_open_tender=False,
        is_active_future_procurement=status in ACTIVE_STATUSES,
        raw=canonical,
    )


def match_plan_to_tender(plan: ProcurementPlanSignal, tender: Mapping):
    """Return a conservative lineage relation or None.

    Buyer/title/value similarity is intentionally insufficient. An explicit source
    relation, matching official procurement reference, or matching OCID is required.
    """
    if not isinstance(tender, Mapping):
        return None
    if _text(tender.get("signal_type") or "TENDER").upper() != "TENDER":
        return None
    explicit = _text(tender.get("plan_reference"))
    plan_refs = {_text(plan.source_ref), _text(plan.raw.get("plan_control_id")), _text(plan.raw.get("ocid"))} - {""}
    tender_refs = {explicit, _text(tender.get("source_reference")), _text(tender.get("ocid"))} - {""}
    shared = plan_refs & tender_refs
    if not shared:
        return None
    reference = sorted(shared)[0]
    return {"relation": "PLAN_TO_TENDER", "plan_signal_id": plan.signal_id, "tender_external_id": _text(tender.get("external_id")), "reference": reference, "confidence": "HIGH"}


def plan_read_model(plan: ProcurementPlanSignal):
    """Product-safe read model; no bid CTA and no fabricated deadline."""
    when = plan.planned_procurement_date.raw or "Unknown"
    return {
        "id": plan.signal_id,
        "label": "Planned procurement",
        "signal_type": plan.signal_type,
        "title": plan.title,
        "buyer": plan.buyer_name,
        "when": when,
        "date_precision": plan.planned_procurement_date.precision,
        "estimated_value": str(plan.estimated_value.estimate) if plan.estimated_value.estimate is not None else None,
        "estimated_value_min": str(plan.estimated_value.minimum) if plan.estimated_value.minimum is not None else None,
        "estimated_value_max": str(plan.estimated_value.maximum) if plan.estimated_value.maximum is not None else None,
        "currency": plan.estimated_value.currency,
        "value_semantics": "ESTIMATED",
        "status": plan.plan_status,
        "active": plan.is_active_future_procurement,
        "confidence": plan.confidence,
        "source": plan.provenance,
        "is_open_tender": False,
        "deadline": None,
        "cta": "View source",
        "uncertainty_note": "Planned procurement is buyer intent, not a guaranteed tender or contract.",
    }
