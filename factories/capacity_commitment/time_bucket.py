from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal, DecimalException, ROUND_HALF_EVEN, localcontext
from enum import Enum
from typing import Iterable

from .engine import CommitmentState


ZERO = Decimal("0")
_CONTEXT = Context(prec=60, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999)


class ExceptionSeverity(str, Enum):
    NONE = "NONE"
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class CommitmentBucket:
    period_id: str
    commitment_state: CommitmentState
    committed_units: Decimal
    actual_units: Decimal
    forecast_units: Decimal | None = None
    alert_tolerance_units: Decimal = ZERO
    alert_tolerance_percent: Decimal = ZERO
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class BucketResult:
    period_id: str
    commitment_state: CommitmentState
    committed_units: Decimal
    actual_units: Decimal
    forecast_units: Decimal | None
    firm_shortfall_units: Decimal
    operational_variance_units: Decimal | None
    alert_threshold_units: Decimal
    outside_alert_tolerance: bool
    severity: ExceptionSeverity
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class ReconciliationResult:
    buckets: tuple[BucketResult, ...]
    firm_committed_units: Decimal
    actual_units_for_firm_periods: Decimal
    firm_shortfall_units: Decimal
    forecast_units: Decimal
    forecast_variance_units: Decimal
    exception_periods: tuple[str, ...]


def _text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    value = value.strip()
    if len(value) > 200 or "\x00" in value:
        raise ValueError(f"{field} is invalid")
    return value


def _decimal(value, field: str) -> Decimal:
    if not isinstance(value, Decimal):
        raise ValueError(f"{field} must be an exact Decimal")
    if not value.is_finite() or value < ZERO:
        raise ValueError(f"{field} must be finite and non-negative")
    return value


def _validate_refs(values) -> tuple[str, ...]:
    if not isinstance(values, tuple) or not all(isinstance(item, str) and item.strip() for item in values):
        raise ValueError("source_refs must be a tuple of non-empty strings")
    normalized = tuple(item.strip() for item in values)
    if len(normalized) > 100 or len(set(normalized)) != len(normalized):
        raise ValueError("source_refs must be unique and at most 100 items")
    return normalized


def validate_bucket(bucket: CommitmentBucket) -> CommitmentBucket:
    if not isinstance(bucket.commitment_state, CommitmentState):
        raise ValueError("commitment_state must be a CommitmentState")
    period_id = _text(bucket.period_id, "period_id")
    committed = _decimal(bucket.committed_units, "committed_units")
    actual = _decimal(bucket.actual_units, "actual_units")
    forecast = None if bucket.forecast_units is None else _decimal(bucket.forecast_units, "forecast_units")
    tolerance_units = _decimal(bucket.alert_tolerance_units, "alert_tolerance_units")
    tolerance_percent = _decimal(bucket.alert_tolerance_percent, "alert_tolerance_percent")
    if tolerance_percent > Decimal("100"):
        raise ValueError("alert_tolerance_percent cannot exceed 100")
    refs = _validate_refs(bucket.source_refs)
    if bucket.commitment_state in {CommitmentState.FORECAST_ONLY, CommitmentState.AMBIGUOUS, CommitmentState.NONE} and committed != ZERO:
        raise ValueError("non-firm bucket must not carry committed_units")
    return CommitmentBucket(
        period_id=period_id,
        commitment_state=bucket.commitment_state,
        committed_units=committed,
        actual_units=actual,
        forecast_units=forecast,
        alert_tolerance_units=tolerance_units,
        alert_tolerance_percent=tolerance_percent,
        source_refs=refs,
    )


def _alert_threshold(bucket: CommitmentBucket) -> Decimal:
    with localcontext(_CONTEXT):
        percentage = bucket.committed_units * bucket.alert_tolerance_percent / Decimal("100")
        return max(bucket.alert_tolerance_units, percentage)


def _severity(shortfall: Decimal, committed: Decimal, outside: bool) -> ExceptionSeverity:
    if not outside or shortfall == ZERO:
        return ExceptionSeverity.NONE
    if committed == ZERO:
        return ExceptionSeverity.INFO
    with localcontext(_CONTEXT):
        ratio = shortfall / committed
    if ratio >= Decimal("0.25"):
        return ExceptionSeverity.CRITICAL
    if ratio >= Decimal("0.10"):
        return ExceptionSeverity.WARNING
    return ExceptionSeverity.INFO


def reconcile_time_buckets(buckets: Iterable[CommitmentBucket]) -> ReconciliationResult:
    """Reconcile commitments and actuals without promoting forecasts into rights.

    Alert tolerances affect exception triage only. They never reduce firm shortfall
    or alter a downstream contractual entitlement calculation.
    """

    validated = [validate_bucket(item) for item in buckets]
    if not validated:
        raise ValueError("at least one commitment bucket is required")
    period_ids = [item.period_id for item in validated]
    if len(set(period_ids)) != len(period_ids):
        raise ValueError("duplicate period_id in commitment buckets")

    results = []
    firm_committed = ZERO
    firm_actual = ZERO
    firm_shortfall_total = ZERO
    forecast_total = ZERO
    forecast_actual_total = ZERO

    try:
        with localcontext(_CONTEXT):
            for bucket in sorted(validated, key=lambda item: item.period_id):
                is_firm = bucket.commitment_state in {CommitmentState.FIRM, CommitmentState.FLEX_WINDOW}
                firm_shortfall = max(bucket.committed_units - bucket.actual_units, ZERO) if is_firm else ZERO
                operational_variance = (
                    bucket.forecast_units - bucket.actual_units if bucket.forecast_units is not None else None
                )
                threshold = _alert_threshold(bucket) if is_firm else ZERO
                outside = is_firm and firm_shortfall > threshold
                severity = _severity(firm_shortfall, bucket.committed_units, outside)
                results.append(
                    BucketResult(
                        period_id=bucket.period_id,
                        commitment_state=bucket.commitment_state,
                        committed_units=bucket.committed_units,
                        actual_units=bucket.actual_units,
                        forecast_units=bucket.forecast_units,
                        firm_shortfall_units=firm_shortfall,
                        operational_variance_units=operational_variance,
                        alert_threshold_units=threshold,
                        outside_alert_tolerance=outside,
                        severity=severity,
                        source_refs=bucket.source_refs,
                    )
                )
                if is_firm:
                    firm_committed += bucket.committed_units
                    firm_actual += bucket.actual_units
                    firm_shortfall_total += firm_shortfall
                if bucket.forecast_units is not None:
                    forecast_total += bucket.forecast_units
                    forecast_actual_total += bucket.actual_units
    except DecimalException as exc:
        raise ValueError("time-bucket arithmetic exceeds supported range") from exc

    return ReconciliationResult(
        buckets=tuple(results),
        firm_committed_units=firm_committed,
        actual_units_for_firm_periods=firm_actual,
        firm_shortfall_units=firm_shortfall_total,
        forecast_units=forecast_total,
        forecast_variance_units=forecast_total - forecast_actual_total,
        exception_periods=tuple(item.period_id for item in results if item.outside_alert_tolerance),
    )
