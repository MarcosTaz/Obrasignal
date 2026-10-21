from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from .models import Evidence, Metric, TruthState
from .registry import append_audit, mutate_company, now_iso
from .security import normalize_source_label

ALLOWED_METRICS = {
    "revenue": {"label": "Revenue", "unit": "EUR", "kind": "money"},
    "pipeline": {"label": "Pipeline", "unit": "EUR", "kind": "money"},
    "customers": {"label": "Customers", "unit": "count", "kind": "count"},
}
RESERVED_METRIC_KEYS = frozenset(ALLOWED_METRICS)
CUSTOM_METRIC_KEY = re.compile(r"[a-z][a-z0-9_.-]{1,63}")
ALLOWED_STATES = {TruthState.GREEN, TruthState.DEGRADED, TruthState.UNKNOWN, TruthState.STALE}


def _observed_at(value: str | None) -> str:
    if value is None:
        value = now_iso()
    elif not isinstance(value, str) or not value.strip():
        raise ValueError("observed_at must be ISO-8601")
    value = value.strip()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    if (parsed - datetime.now(timezone.utc)).total_seconds() > 300:
        raise ValueError("future-dated business metric evidence rejected")
    return parsed.isoformat()


def _freshness(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("freshness_seconds must be an integer")
    return max(60, min(value, 7 * 24 * 3600))


def _truth_state(state: str, value: Any) -> TruthState:
    try:
        truth_state = TruthState(str(state).strip().upper())
    except ValueError as exc:
        raise ValueError("state must be GREEN, DEGRADED, UNKNOWN or STALE") from exc
    if truth_state not in ALLOWED_STATES:
        raise ValueError("invalid metric state")
    if value is None:
        return TruthState.UNKNOWN
    return truth_state


def _effective_state(requested: TruthState, evidence: Evidence) -> TruthState:
    """Never return a stronger current state than the evidence freshness supports."""
    if requested == TruthState.UNKNOWN:
        return requested
    freshness = evidence.freshness_state()
    return requested if freshness == TruthState.GREEN else freshness


def _normalized_value(metric_key: str, value: Any) -> int | float | None:
    if value is None:
        return None
    spec = ALLOWED_METRICS[metric_key]
    if spec["kind"] == "count":
        if isinstance(value, bool):
            raise ValueError("customers must be a non-negative integer")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("customers must be a non-negative integer") from exc
        if parsed < 0 or str(parsed) != str(value).strip():
            raise ValueError("customers must be a non-negative integer")
        return parsed
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{metric_key} must be a non-negative number") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{metric_key} must be a non-negative number")
    return float(parsed)


def _canonical_business_unit(metric_key: str, unit: Any) -> str:
    canonical = ALLOWED_METRICS[metric_key]["unit"]
    if unit is None or (isinstance(unit, str) and not unit.strip()):
        return canonical
    if not isinstance(unit, str) or unit.strip().lower() != canonical.lower():
        raise ValueError(f"{metric_key} unit must be {canonical}; conversion is not performed by this feed")
    return canonical


def _normalized_custom_unit(unit: Any) -> str | None:
    if unit is None:
        return None
    if not isinstance(unit, str):
        raise ValueError("unit must be a string or null")
    value = unit.strip()
    if not value:
        return None
    if len(value) > 32:
        raise ValueError("unit must be at most 32 characters")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("unit contains unsafe characters")
    return value


def _normalized_detail(detail: Any, default: str) -> str:
    if detail is None:
        return default
    if not isinstance(detail, str):
        raise ValueError("detail must be a string or null")
    value = detail.strip()
    if not value:
        return default
    if len(value) > 1000:
        raise ValueError("detail must be at most 1000 characters")
    return value


def _normalized_custom_value(value: Any) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("metric value must be a finite number or null")
    if isinstance(value, int):
        return value
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("metric value must be a finite number or null") from exc
    if not math.isfinite(parsed):
        raise ValueError("metric value must be a finite number or null")
    return parsed


def _metric_fingerprint(metric: Metric) -> tuple:
    evidence = metric.evidence
    return (
        metric.label,
        metric.value,
        metric.unit,
        metric.state.value,
        evidence.source if evidence else None,
        evidence.freshness_seconds if evidence else None,
        evidence.detail if evidence else None,
    )


def _validate_observation_order(existing: Metric, incoming: Metric, authoritative_kinds: set[str]) -> None:
    """Reject older evidence and contradictory writes at the same observation time."""
    if not existing.evidence or existing.evidence.kind not in authoritative_kinds or not existing.evidence.observed_at:
        return
    if not incoming.evidence or not incoming.evidence.observed_at:
        return
    try:
        current = datetime.fromisoformat(existing.evidence.observed_at.replace("Z", "+00:00"))
        new = datetime.fromisoformat(incoming.evidence.observed_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if new.tzinfo is None:
        new = new.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    new = new.astimezone(timezone.utc)
    if new < current:
        raise ValueError("out-of-order business metric evidence rejected")
    if new == current and _metric_fingerprint(existing) != _metric_fingerprint(incoming):
        raise ValueError("conflicting business metric evidence at identical observed_at rejected")


def ingest_business_metric(
    *,
    company_id: str,
    metric_key: str,
    value: Any,
    source: str,
    observed_at: str | None = None,
    freshness_seconds: int = 3600,
    state: str = "GREEN",
    unit: str | None = None,
    detail: str | None = None,
) -> Metric:
    """Ingest one canonical business metric with explicit source/freshness evidence."""
    metric_key = str(metric_key).strip().lower()
    if metric_key not in ALLOWED_METRICS:
        raise ValueError("metric_key must be one of: revenue, pipeline, customers")
    source_label = normalize_source_label(source)
    observed = _observed_at(observed_at)
    freshness = _freshness(freshness_seconds)
    normalized = _normalized_value(metric_key, value)
    requested_state = _truth_state(state, normalized)
    spec = ALLOWED_METRICS[metric_key]
    canonical_unit = _canonical_business_unit(metric_key, unit)
    evidence = Evidence(
        source=source_label,
        observed_at=observed,
        freshness_seconds=freshness,
        kind="business_metric_feed",
        detail=_normalized_detail(detail, "Authenticated canonical business metric feed."),
    )
    effective_state = _effective_state(requested_state, evidence)
    metric = Metric(metric_key, spec["label"], normalized, canonical_unit, effective_state, evidence)

    def apply(company):
        existing = getattr(company, metric_key)
        _validate_observation_order(existing, metric, {"business_metric_feed"})
        setattr(company, metric_key, metric)
        return metric

    _, metric = mutate_company(company_id, apply)
    append_audit(
        actor="business_metric_feed",
        action="ingest_business_metric",
        level="GREEN",
        company_id=company_id,
        result=f"{metric_key}_ingested_{effective_state.value.lower()}",
        source_data={"metric_key": metric_key, "source": evidence.source, "observed_at": observed, "freshness_seconds": freshness, "state": effective_state.value},
    )
    return metric


def ingest_operational_metric(
    *,
    company_id: str,
    metric_key: str,
    label: str,
    value: Any,
    source: str,
    observed_at: str | None = None,
    freshness_seconds: int = 3600,
    state: str = "GREEN",
    unit: str | None = None,
    detail: str | None = None,
) -> Metric:
    """Ingest a source-owned numeric KPI without promoting it to business truth."""
    metric_key = str(metric_key).strip().lower()
    if not CUSTOM_METRIC_KEY.fullmatch(metric_key) or metric_key in RESERVED_METRIC_KEYS:
        raise ValueError("metric_key must be a 2-64 character KPI slug and not a reserved business metric")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("label is required")
    label = label.strip()
    if len(label) > 120:
        raise ValueError("label must be at most 120 characters")
    source_label = normalize_source_label(source)
    observed = _observed_at(observed_at)
    freshness = _freshness(freshness_seconds)
    normalized = _normalized_custom_value(value)
    normalized_unit = _normalized_custom_unit(unit)
    requested_state = _truth_state(state, normalized)
    evidence = Evidence(
        source=source_label,
        observed_at=observed,
        freshness_seconds=freshness,
        kind="operational_metric_feed",
        detail=_normalized_detail(detail, "Authenticated source-owned operational KPI feed."),
    )
    effective_state = _effective_state(requested_state, evidence)
    metric = Metric(
        key=metric_key,
        label=label,
        value=normalized,
        unit=normalized_unit,
        state=effective_state,
        evidence=evidence,
    )

    def apply(company):
        existing = next((item for item in company.metrics if item.key == metric_key), None)
        if existing is not None:
            _validate_observation_order(existing, metric, {"operational_metric_feed"})
        company.metrics = [item for item in company.metrics if item.key != metric_key] + [metric]
        return metric

    _, metric = mutate_company(company_id, apply)
    append_audit(
        actor="operational_metric_feed",
        action="ingest_operational_metric",
        level="GREEN",
        company_id=company_id,
        result=f"{metric_key}_ingested_{effective_state.value.lower()}",
        source_data={"metric_key": metric_key, "source": evidence.source, "observed_at": observed, "freshness_seconds": freshness, "state": effective_state.value},
    )
    return metric
