"""Deterministic opportunity record completeness evaluation.

Answers only: "what do we know about this opportunity record?" It does not
score commercial quality, win probability, relevance, readiness, economic fit,
or recommendation confidence. V0 is an on-demand pure evaluator over
canonical/normalized mappings with no storage, enrichment, or external calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable, Literal, Mapping
import re

FieldState = Literal[
    "AVAILABLE", "MISSING", "UNKNOWN", "INVALID", "STALE",
    "NOT_APPLICABLE", "NOT_PROVIDED_BY_SOURCE",
]
POLICY_VERSION = "opportunity-data-quality.v0"
MAX_COVERAGE_NOTE_LENGTH = 1000


@dataclass(frozen=True)
class FieldDefinition:
    key: str
    label: str
    critical: bool = False
    extractor: Callable[[Mapping], object | None] | None = None
    applicable: Callable[[Mapping, Mapping], bool] | None = None
    validator: Callable[[object], bool] | None = None
    freshness_timestamp: bool = False


@dataclass(frozen=True)
class DataQualityPolicy:
    version: str = POLICY_VERSION
    stale_after_days: int | None = None

    def __post_init__(self) -> None:
        if not self.version or not str(self.version).strip():
            raise ValueError("policy version is required")
        if self.stale_after_days is not None and self.stale_after_days < 0:
            raise ValueError("stale_after_days must be non-negative")


@dataclass(frozen=True)
class OpportunityDataQuality:
    opportunity_id: str
    available_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    unknown_fields: tuple[str, ...]
    invalid_fields: tuple[str, ...]
    stale_fields: tuple[str, ...]
    critical_missing_fields: tuple[str, ...]
    not_applicable_fields: tuple[str, ...]
    not_provided_by_source_fields: tuple[str, ...]
    completeness_ratio: float
    generated_at: str
    policy_version: str
    source_coverage_notes: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "opportunity_id": self.opportunity_id,
            "summary": {
                "applicable_expected": (
                    len(self.available_fields) + len(self.missing_fields)
                    + len(self.unknown_fields) + len(self.invalid_fields)
                    + len(self.stale_fields)
                ),
                "present": len(self.available_fields) + len(self.stale_fields),
                "completeness_ratio": self.completeness_ratio,
            },
            "available": list(self.available_fields),
            "missing": list(self.missing_fields),
            "unknown": list(self.unknown_fields),
            "invalid": list(self.invalid_fields),
            "stale": list(self.stale_fields),
            "critical_missing": list(self.critical_missing_fields),
            "not_applicable": list(self.not_applicable_fields),
            "not_provided_by_source": list(self.not_provided_by_source_fields),
            "policy_version": self.policy_version,
            "generated_at": self.generated_at,
            "source_coverage_notes": list(self.source_coverage_notes),
        }


def _usable(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return bool(value)
    return True


def _first(record: Mapping, *keys: str):
    for key in keys:
        value = record.get(key)
        if _usable(value):
            return value
    return None


def _valid_identifier(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and len(text) <= 512 and "\x00" not in text


def _valid_text(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and len(text) <= 100_000 and "\x00" not in text


def _valid_url(value: object) -> bool:
    text = str(value or "").strip()
    return bool(re.match(r"^https?://[^\s]+$", text, flags=re.IGNORECASE)) and len(text) <= 4096


def _parse_datetime(value: object) -> datetime | None:
    if not _usable(value):
        return None
    text = str(value).strip().replace("Z", "+00:00")
    for candidate in (text, text[:10], text[:8]):
        try:
            if len(candidate) == 8 and candidate.isdigit():
                dt = datetime.strptime(candidate, "%Y%m%d")
            else:
                dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


def _valid_datetime(value: object) -> bool:
    return _parse_datetime(value) is not None


def _valid_currency(value: object) -> bool:
    return bool(re.fullmatch(r"[A-Za-z]{3}", str(value or "").strip()))


def _valid_money(value: object) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value)) >= 0
        except InvalidOperation:
            return False
    text = str(value).strip()
    if not text:
        return False
    match = re.search(r"[-+]?\d[\d\s.,]*", text)
    if not match:
        return False
    number = match.group(0).replace(" ", "")
    if number.count(",") and number.count("."):
        if number.rfind(",") > number.rfind("."):
            number = number.replace(".", "").replace(",", ".")
        else:
            number = number.replace(",", "")
    elif number.count(",") == 1 and len(number.rsplit(",", 1)[1]) <= 2:
        number = number.replace(",", ".")
    else:
        number = number.replace(",", "")
    try:
        return Decimal(number) >= 0
    except InvalidOperation:
        return False


def _location(record: Mapping):
    return _first(record, "place", "country")


def _identity(record: Mapping):
    return _first(record, "external_id", "opportunity_id")


def _category(record: Mapping):
    return _first(record, "category_code", "cpv", "taxonomy")


def _provenance(record: Mapping):
    return _first(record, "source_reference", "url")


def _updated_at(record: Mapping):
    return _first(
        record, "source_updated_at", "lifecycle_source_updated_at",
        "last_observed", "last_seen",
    )


def _separate_currency_applicable(record: Mapping, context: Mapping) -> bool:
    return "currency" in record or "currency" in set(context.get("expected_fields") or ())


def _deadline_applicable(record: Mapping, context: Mapping) -> bool:
    signal_type = str(
        record.get("signal_type") or context.get("signal_type") or "TENDER"
    ).strip().upper()
    return signal_type in {"TENDER", "FORECAST"} or "deadline" in set(
        context.get("expected_fields") or ()
    )


def _updated_at_applicable(record: Mapping, context: Mapping) -> bool:
    return _updated_at(record) is not None or "updated_at" in set(
        context.get("expected_fields") or ()
    )


FIELD_REGISTRY: tuple[FieldDefinition, ...] = (
    FieldDefinition("source", "Source", True, lambda r: r.get("source"), validator=_valid_identifier),
    FieldDefinition("opportunity_identity", "Opportunity identity", True, _identity, validator=_valid_identifier),
    FieldDefinition("title", "Title", True, lambda r: r.get("title"), validator=_valid_text),
    FieldDefinition("buyer", "Buyer", False, lambda r: r.get("buyer"), validator=_valid_text),
    FieldDefinition("location", "Location", False, _location, validator=_valid_text),
    FieldDefinition("deadline", "Deadline", False, lambda r: r.get("deadline"), applicable=_deadline_applicable, validator=_valid_datetime),
    FieldDefinition("published_value", "Published value", False, lambda r: r.get("value"), validator=_valid_money),
    FieldDefinition("currency", "Currency", False, lambda r: r.get("currency"), applicable=_separate_currency_applicable, validator=_valid_currency),
    FieldDefinition("description", "Description", False, lambda r: r.get("description"), validator=_valid_text),
    FieldDefinition("category", "Category", False, _category, validator=_valid_text),
    FieldDefinition("publication_date", "Publication date", False, lambda r: _first(r, "publication_date", "published_at"), validator=_valid_datetime),
    FieldDefinition("provenance", "Provenance", True, _provenance, validator=lambda v: _valid_url(v) or _valid_identifier(v)),
    FieldDefinition("updated_at", "Source updated at", False, _updated_at, applicable=_updated_at_applicable, validator=_valid_datetime, freshness_timestamp=True),
)


def _bounded_notes(context: Mapping) -> tuple[str, ...]:
    raw = context.get("source_coverage_notes") or ()
    if isinstance(raw, str):
        raw = (raw,)
    notes = []
    for item in raw:
        text = str(item).replace("\x00", "").strip()
        if text:
            notes.append(text[:MAX_COVERAGE_NOTE_LENGTH])
    return tuple(notes[:20])


def _iso_utc(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    dt = _parse_datetime(value)
    if dt is None:
        raise ValueError("evaluated_at must be a valid datetime")
    return dt.isoformat()


def evaluate_opportunity_data_quality(
    opportunity: Mapping,
    source_context: Mapping | None = None,
    policy: DataQualityPolicy | None = None,
    *,
    evaluated_at: datetime | str | None = None,
) -> OpportunityDataQuality:
    """Evaluate one normalized record without mutation or external enrichment.

    Source context can explicitly declare unknown fields and publisher structural
    omissions. Freshness is applied only to a registered timestamp when the
    policy explicitly defines a stale threshold. Stale means present-but-old and
    therefore remains present for the completeness ratio.
    """
    if not isinstance(opportunity, Mapping):
        raise TypeError("opportunity must be a mapping")
    context = {} if source_context is None else source_context
    if not isinstance(context, Mapping):
        raise TypeError("source_context must be a mapping")
    active_policy = policy or DataQualityPolicy()
    if not isinstance(active_policy, DataQualityPolicy):
        raise TypeError("policy must be a DataQualityPolicy")

    generated_at = _iso_utc(evaluated_at)
    evaluated_dt = _parse_datetime(generated_at)
    assert evaluated_dt is not None
    unknown_declared = {str(key) for key in context.get("unknown_fields") or ()}
    unavailable_declared = {str(key) for key in context.get("not_provided_fields") or ()}

    buckets: dict[FieldState, list[str]] = {
        "AVAILABLE": [], "MISSING": [], "UNKNOWN": [], "INVALID": [],
        "STALE": [], "NOT_APPLICABLE": [], "NOT_PROVIDED_BY_SOURCE": [],
    }
    critical_missing: list[str] = []

    for definition in FIELD_REGISTRY:
        applicable = (
            definition.applicable(opportunity, context)
            if definition.applicable else True
        )
        if not applicable:
            state: FieldState = "NOT_APPLICABLE"
        elif definition.key in unavailable_declared:
            state = "NOT_PROVIDED_BY_SOURCE"
        elif definition.key in unknown_declared:
            state = "UNKNOWN"
        else:
            value = (
                definition.extractor(opportunity)
                if definition.extractor else opportunity.get(definition.key)
            )
            if not _usable(value):
                state = "MISSING"
            elif definition.validator and not definition.validator(value):
                state = "INVALID"
            elif (
                definition.freshness_timestamp
                and active_policy.stale_after_days is not None
                and (timestamp := _parse_datetime(value)) is not None
                and (evaluated_dt - timestamp).total_seconds()
                    > active_policy.stale_after_days * 86400
            ):
                state = "STALE"
            else:
                state = "AVAILABLE"
        buckets[state].append(definition.key)
        if definition.critical and state in {"MISSING", "UNKNOWN", "INVALID", "STALE"}:
            critical_missing.append(definition.key)

    denominator = sum(
        len(buckets[state])
        for state in ("AVAILABLE", "MISSING", "UNKNOWN", "INVALID", "STALE")
    )
    present = len(buckets["AVAILABLE"]) + len(buckets["STALE"])
    ratio = round(present / denominator, 4) if denominator else 1.0

    return OpportunityDataQuality(
        opportunity_id=str(_identity(opportunity) or "").strip(),
        available_fields=tuple(buckets["AVAILABLE"]),
        missing_fields=tuple(buckets["MISSING"]),
        unknown_fields=tuple(buckets["UNKNOWN"]),
        invalid_fields=tuple(buckets["INVALID"]),
        stale_fields=tuple(buckets["STALE"]),
        critical_missing_fields=tuple(critical_missing),
        not_applicable_fields=tuple(buckets["NOT_APPLICABLE"]),
        not_provided_by_source_fields=tuple(buckets["NOT_PROVIDED_BY_SOURCE"]),
        completeness_ratio=ratio,
        generated_at=generated_at,
        policy_version=active_policy.version,
        source_coverage_notes=_bounded_notes(context),
    )
