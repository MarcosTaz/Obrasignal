"""Canonical procurement milestone model and deterministic read helpers.

No alerts, recommendations, live fetches, source mutation, or workflow actions live
here. Source adapters provide facts; this capability preserves temporal semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Iterable, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

NORMALIZER_VERSION = "milestones.v0"
MAX_LABEL_LENGTH = 500


class MilestoneType(str, Enum):
    PUBLICATION = "PUBLICATION"
    DOCUMENT_AVAILABLE = "DOCUMENT_AVAILABLE"
    SITE_VISIT = "SITE_VISIT"
    SITE_VISIT_REGISTRATION = "SITE_VISIT_REGISTRATION"
    CLARIFICATION_OPEN = "CLARIFICATION_OPEN"
    CLARIFICATION_DEADLINE = "CLARIFICATION_DEADLINE"
    QUESTIONS_DEADLINE = "QUESTIONS_DEADLINE"
    EOI_DEADLINE = "EOI_DEADLINE"
    QUALIFICATION_DEADLINE = "QUALIFICATION_DEADLINE"
    BID_SUBMISSION_DEADLINE = "BID_SUBMISSION_DEADLINE"
    BID_OPENING = "BID_OPENING"
    BID_VALIDITY_END = "BID_VALIDITY_END"
    STANDSTILL_END = "STANDSTILL_END"
    EXPECTED_AWARD = "EXPECTED_AWARD"
    AWARD = "AWARD"
    CONTRACT_SIGNING = "CONTRACT_SIGNING"
    EXPECTED_CONTRACT_START = "EXPECTED_CONTRACT_START"
    CONTRACT_START = "CONTRACT_START"
    GUARANTEE_DEADLINE = "GUARANTEE_DEADLINE"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class DateBasis(str, Enum):
    OFFICIAL = "OFFICIAL"
    SOURCE_DERIVED = "SOURCE_DERIVED"
    SYSTEM_DERIVED = "SYSTEM_DERIVED"
    USER_ENTERED = "USER_ENTERED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class DatePrecision(str, Enum):
    EXACT_DATETIME = "EXACT_DATETIME"
    DATE = "DATE"
    MONTH = "MONTH"
    QUARTER = "QUARTER"
    YEAR = "YEAR"
    RANGE = "RANGE"
    APPROXIMATE = "APPROXIMATE"
    UNKNOWN = "UNKNOWN"


class RequirementLevel(str, Enum):
    MANDATORY = "MANDATORY"
    OPTIONAL = "OPTIONAL"
    UNKNOWN = "UNKNOWN"


class ResolutionState(str, Enum):
    CURRENT = "CURRENT"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"


TYPE_REGISTRY: dict[MilestoneType, dict[str, object]] = {
    kind: {
        "label": kind.value.replace("_", " ").title(),
        "critical": kind in {
            MilestoneType.SITE_VISIT_REGISTRATION,
            MilestoneType.QUESTIONS_DEADLINE,
            MilestoneType.EOI_DEADLINE,
            MilestoneType.QUALIFICATION_DEADLINE,
            MilestoneType.BID_SUBMISSION_DEADLINE,
            MilestoneType.GUARANTEE_DEADLINE,
        },
    }
    for kind in MilestoneType
}

FIELD_REGISTRY: dict[str, MilestoneType] = {
    "publication_date": MilestoneType.PUBLICATION,
    "published_at": MilestoneType.PUBLICATION,
    "deadline": MilestoneType.BID_SUBMISSION_DEADLINE,
    "submission_date": MilestoneType.BID_SUBMISSION_DEADLINE,
    "closing_date": MilestoneType.BID_SUBMISSION_DEADLINE,
    "opening_date": MilestoneType.BID_OPENING,
    "site_visit": MilestoneType.SITE_VISIT,
    "site_visit_registration_deadline": MilestoneType.SITE_VISIT_REGISTRATION,
    "clarification_open": MilestoneType.CLARIFICATION_OPEN,
    "clarification_deadline": MilestoneType.CLARIFICATION_DEADLINE,
    "question_deadline": MilestoneType.QUESTIONS_DEADLINE,
    "questions_deadline": MilestoneType.QUESTIONS_DEADLINE,
    "eoi_deadline": MilestoneType.EOI_DEADLINE,
    "qualification_deadline": MilestoneType.QUALIFICATION_DEADLINE,
    "bid_validity_end": MilestoneType.BID_VALIDITY_END,
    "standstill_end": MilestoneType.STANDSTILL_END,
    "expected_award": MilestoneType.EXPECTED_AWARD,
    "award_date": MilestoneType.AWARD,
    "contract_signing": MilestoneType.CONTRACT_SIGNING,
    "expected_contract_start": MilestoneType.EXPECTED_CONTRACT_START,
    "contract_start": MilestoneType.CONTRACT_START,
    "guarantee_deadline": MilestoneType.GUARANTEE_DEADLINE,
}


def _text(value) -> str:
    return str(value or "").strip()


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _validate_partial(precision: DatePrecision, value: str) -> None:
    if precision == DatePrecision.EXACT_DATETIME:
        _parse_datetime(value)
    elif precision == DatePrecision.DATE:
        date.fromisoformat(value)
    elif precision == DatePrecision.MONTH:
        if len(value) != 7 or value[4] != "-" or not value[:4].isdigit() or not value[5:].isdigit() or not 1 <= int(value[5:]) <= 12:
            raise ValueError(f"invalid month: {value}")
    elif precision == DatePrecision.QUARTER:
        parts = value.upper().split()
        if len(parts) != 2 or parts[0] not in {"Q1", "Q2", "Q3", "Q4"} or not parts[1].isdigit():
            raise ValueError(f"invalid quarter: {value}")
    elif precision == DatePrecision.YEAR:
        if len(value) != 4 or not value.isdigit():
            raise ValueError(f"invalid year: {value}")


def _range_order(value: str) -> tuple[int, str]:
    text = _text(value)
    try:
        parsed = _parse_datetime(text)
        if parsed.tzinfo:
            return (0, parsed.astimezone(timezone.utc).isoformat())
        return (0, parsed.isoformat())
    except ValueError:
        pass
    try:
        return (1, date.fromisoformat(text).isoformat())
    except ValueError:
        return (2, text)


@dataclass(frozen=True)
class TemporalValue:
    precision: DatePrecision
    value: str | None = None
    start: str | None = None
    end: str | None = None
    timezone_name: str | None = None

    def __post_init__(self):
        if self.precision == DatePrecision.RANGE:
            if not self.start or not self.end:
                raise ValueError("RANGE requires start and end")
            if _range_order(self.start) > _range_order(self.end):
                raise ValueError("invalid date range: start is after end")
        elif self.precision != DatePrecision.UNKNOWN:
            if not self.value:
                raise ValueError(f"{self.precision.value} requires value")
            _validate_partial(self.precision, self.value)
        if self.timezone_name:
            try:
                ZoneInfo(self.timezone_name)
            except ZoneInfoNotFoundError as exc:
                raise ValueError(f"invalid timezone: {self.timezone_name}") from exc


@dataclass(frozen=True)
class ProcurementMilestone:
    milestone_id: str
    opportunity_id: str
    milestone_type: MilestoneType
    temporal: TemporalValue
    basis: DateBasis = DateBasis.OFFICIAL
    requirement_level: RequirementLevel = RequirementLevel.UNKNOWN
    source: str = ""
    source_ref: str = ""
    source_field: str = ""
    native_label: str = ""
    lot_id: str = ""
    stage: str = ""
    confidence: float = 1.0
    supersedes_milestone_id: str | None = None
    cancelled: bool = False
    revision_key: str = ""
    normalizer_version: str = NORMALIZER_VERSION

    def __post_init__(self):
        if not self.opportunity_id:
            raise ValueError("opportunity_id is required")
        if not self.milestone_id:
            raise ValueError("milestone_id is required")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if len(self.native_label) > MAX_LABEL_LENGTH:
            raise ValueError("native_label exceeds maximum length")

    @property
    def fingerprint(self) -> str:
        material = "|".join((
            self.opportunity_id, self.lot_id, self.stage, self.milestone_type.value,
            self.temporal.precision.value, self.temporal.value or "", self.temporal.start or "",
            self.temporal.end or "", self.temporal.timezone_name or "", self.basis.value,
            self.source, self.source_ref, self.source_field,
        ))
        return sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MilestoneView:
    milestone: ProcurementMilestone
    resolution: ResolutionState
    temporal_status: str


def _infer_temporal(value, *, timezone_name=None, precision=None) -> TemporalValue:
    if isinstance(value, Mapping):
        p = DatePrecision(_text(value.get("precision") or precision or "UNKNOWN").upper())
        return TemporalValue(
            p,
            value=_text(value.get("value")) or None,
            start=_text(value.get("start")) or None,
            end=_text(value.get("end")) or None,
            timezone_name=_text(value.get("timezone") or timezone_name) or None,
        )
    text = _text(value)
    if not text:
        return TemporalValue(DatePrecision.UNKNOWN)
    if precision:
        p = DatePrecision(_text(precision).upper())
    elif "T" in text or (":" in text and len(text) >= 13):
        p = DatePrecision.EXACT_DATETIME
    elif len(text) == 10 and text[4:5] == "-" and text[7:8] == "-":
        p = DatePrecision.DATE
    elif len(text) == 7 and text[4:5] == "-":
        p = DatePrecision.MONTH
    elif text.upper().startswith("Q") and len(text.split()) == 2:
        p = DatePrecision.QUARTER
    elif len(text) == 4 and text.isdigit():
        p = DatePrecision.YEAR
    else:
        p = DatePrecision.APPROXIMATE
    return TemporalValue(p, value=text, timezone_name=_text(timezone_name) or None)


def _milestone_id(opportunity_id: str, kind: MilestoneType, temporal: TemporalValue, *, lot_id="", stage="", source_ref="", source_field="") -> str:
    material = "|".join((
        opportunity_id, lot_id, stage, kind.value, temporal.precision.value,
        temporal.value or "", temporal.start or "", temporal.end or "",
        temporal.timezone_name or "", source_ref, source_field,
    ))
    return sha256(material.encode("utf-8")).hexdigest()[:24]


def _from_explicit(opportunity_id: str, item: Mapping, record: Mapping) -> ProcurementMilestone:
    kind = MilestoneType(_text(item.get("type") or "UNKNOWN").upper())
    temporal_raw = item.get("temporal") if isinstance(item.get("temporal"), Mapping) else item.get("value")
    if temporal_raw is None and (item.get("start") or item.get("end")):
        temporal_raw = {
            "precision": "RANGE", "start": item.get("start"), "end": item.get("end"),
            "timezone": item.get("timezone"),
        }
    temporal = _infer_temporal(temporal_raw, timezone_name=item.get("timezone"), precision=item.get("precision"))
    source_ref = _text(item.get("source_ref") or record.get("source_reference") or record.get("external_id"))
    source_field = _text(item.get("source_field"))
    lot_id = _text(item.get("lot_id"))
    stage = _text(item.get("stage"))
    mid = _text(item.get("milestone_id")) or _milestone_id(
        opportunity_id, kind, temporal, lot_id=lot_id, stage=stage,
        source_ref=source_ref, source_field=source_field,
    )
    return ProcurementMilestone(
        milestone_id=mid,
        opportunity_id=opportunity_id,
        milestone_type=kind,
        temporal=temporal,
        basis=DateBasis(_text(item.get("basis") or "OFFICIAL").upper()),
        requirement_level=RequirementLevel(_text(item.get("requirement_level") or "UNKNOWN").upper()),
        source=_text(item.get("source") or record.get("source")),
        source_ref=source_ref,
        source_field=source_field,
        native_label=_text(item.get("native_label")),
        lot_id=lot_id,
        stage=stage,
        confidence=float(item.get("confidence", 1.0)),
        supersedes_milestone_id=_text(item.get("supersedes_milestone_id")) or None,
        cancelled=bool(item.get("cancelled", False)),
        revision_key=_text(item.get("revision_key")),
    )


def normalize_milestones(source_record: Mapping) -> tuple[ProcurementMilestone, ...]:
    """Normalize an already-ingested source record without mutating it."""
    if not isinstance(source_record, Mapping):
        raise TypeError("source_record must be a mapping")
    opportunity_id = _text(source_record.get("opportunity_id") or source_record.get("external_id"))
    if not opportunity_id:
        raise ValueError("source_record requires opportunity_id or external_id")

    out: list[ProcurementMilestone] = []
    explicit = source_record.get("milestones")
    if isinstance(explicit, (list, tuple)):
        out.extend(_from_explicit(opportunity_id, item, source_record) for item in explicit if isinstance(item, Mapping))

    occupied_unscoped_types = {(m.milestone_type, m.lot_id, m.stage) for m in out}
    for field, kind in FIELD_REGISTRY.items():
        raw = source_record.get(field)
        if raw in (None, "") or (kind, "", "") in occupied_unscoped_types:
            continue
        temporal = _infer_temporal(raw, timezone_name=source_record.get(f"{field}_timezone"))
        source_ref = _text(source_record.get("source_reference") or source_record.get("external_id"))
        requirement = RequirementLevel.UNKNOWN
        if kind == MilestoneType.SITE_VISIT:
            marker = source_record.get("site_visit_mandatory")
            requirement = RequirementLevel.MANDATORY if marker is True else RequirementLevel.OPTIONAL if marker is False else RequirementLevel.UNKNOWN
        out.append(ProcurementMilestone(
            milestone_id=_milestone_id(opportunity_id, kind, temporal, source_ref=source_ref, source_field=field),
            opportunity_id=opportunity_id,
            milestone_type=kind,
            temporal=temporal,
            basis=DateBasis.OFFICIAL,
            requirement_level=requirement,
            source=_text(source_record.get("source")),
            source_ref=source_ref,
            source_field=field,
            native_label=field,
            revision_key=_text(source_record.get("amendment_number") or source_record.get("source_updated_at")),
        ))
        occupied_unscoped_types.add((kind, "", ""))

    deduped: list[ProcurementMilestone] = []
    fingerprints: set[str] = set()
    for milestone in out:
        if milestone.fingerprint not in fingerprints:
            fingerprints.add(milestone.fingerprint)
            deduped.append(milestone)
    return tuple(sorted(deduped, key=lambda m: (
        m.milestone_type.value, m.lot_id, m.stage,
        _range_order(m.temporal.value or m.temporal.start or ""), m.milestone_id,
    )))


def resolve_current_milestones(milestones: Iterable[ProcurementMilestone], *, now: datetime) -> tuple[MilestoneView, ...]:
    """Resolve explicit supersession/conflicts while preserving full history."""
    if now.tzinfo is None:
        raise ValueError("injected clock must be timezone-aware")
    items = tuple(milestones)
    ids = {m.milestone_id for m in items}
    for m in items:
        if m.supersedes_milestone_id and m.supersedes_milestone_id not in ids:
            raise ValueError(f"superseded milestone not present: {m.supersedes_milestone_id}")
    superseded = {m.supersedes_milestone_id for m in items if m.supersedes_milestone_id}
    groups: dict[tuple, list[ProcurementMilestone]] = {}
    for m in items:
        groups.setdefault((m.opportunity_id, m.lot_id, m.stage, m.milestone_type), []).append(m)

    views: list[MilestoneView] = []
    for group in groups.values():
        active = [m for m in group if m.milestone_id not in superseded and not m.cancelled]
        distinct_values = {
            (m.temporal.precision, m.temporal.value, m.temporal.start, m.temporal.end, m.temporal.timezone_name)
            for m in active
        }
        conflict = len(active) > 1 and len(distinct_values) > 1
        for m in group:
            resolution = (
                ResolutionState.CANCELLED if m.cancelled else
                ResolutionState.SUPERSEDED if m.milestone_id in superseded else
                ResolutionState.NEEDS_VERIFICATION if conflict else
                ResolutionState.CURRENT
            )
            views.append(MilestoneView(m, resolution, temporal_status(m, now=now)))
    return tuple(sorted(views, key=lambda v: (
        v.milestone.milestone_type.value, v.milestone.lot_id,
        v.milestone.stage, v.milestone.milestone_id,
    )))


def _exact_instant(temporal: TemporalValue) -> datetime | None:
    if temporal.precision != DatePrecision.EXACT_DATETIME or not temporal.value:
        return None
    parsed = _parse_datetime(temporal.value)
    if parsed.tzinfo is None:
        if not temporal.timezone_name:
            return None
        parsed = parsed.replace(tzinfo=ZoneInfo(temporal.timezone_name))
    return parsed.astimezone(timezone.utc)


def temporal_status(milestone: ProcurementMilestone, *, now: datetime) -> str:
    if now.tzinfo is None:
        raise ValueError("injected clock must be timezone-aware")
    temporal = milestone.temporal
    instant = _exact_instant(temporal)
    if instant is not None:
        current = now.astimezone(timezone.utc)
        if instant < current:
            return "PASSED"
        if instant.date() == current.date():
            return "TODAY"
        return "UPCOMING"
    if temporal.precision == DatePrecision.DATE and temporal.value:
        target = date.fromisoformat(temporal.value)
        current_date = now.date()
        return "PASSED" if target < current_date else "TODAY" if target == current_date else "UPCOMING"
    return "UNKNOWN"


def _next_order(milestone: ProcurementMilestone) -> tuple[int, object]:
    instant = _exact_instant(milestone.temporal)
    if instant is not None:
        return (0, instant)
    if milestone.temporal.precision == DatePrecision.DATE and milestone.temporal.value:
        return (1, date.fromisoformat(milestone.temporal.value))
    return (2, milestone.milestone_id)


def next_upcoming_milestone(milestones: Iterable[ProcurementMilestone], *, now: datetime) -> ProcurementMilestone | None:
    current = [
        view.milestone
        for view in resolve_current_milestones(milestones, now=now)
        if view.resolution == ResolutionState.CURRENT
        and view.temporal_status in {"TODAY", "UPCOMING"}
        and view.milestone.temporal.precision in {DatePrecision.EXACT_DATETIME, DatePrecision.DATE}
    ]
    return min(current, key=_next_order) if current else None
