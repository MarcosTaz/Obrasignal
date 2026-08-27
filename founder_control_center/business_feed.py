from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from .models import Evidence, Metric, TruthState
from .registry import append_audit, mutate_company, now_iso

ALLOWED_METRICS = {
    "revenue": {"label": "Revenue", "unit": "EUR", "kind": "money"},
    "pipeline": {"label": "Pipeline", "unit": "EUR", "kind": "money"},
    "customers": {"label": "Customers", "unit": "count", "kind": "count"},
}
ALLOWED_STATES = {TruthState.GREEN, TruthState.DEGRADED, TruthState.UNKNOWN, TruthState.STALE}


def _observed_at(value: str | None) -> str:
    value = value or now_iso()
    if not isinstance(value, str):
        raise ValueError("observed_at must be ISO-8601")
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
    try:
        return max(60, min(int(value), 7 * 24 * 3600))
    except (TypeError, ValueError) as exc:
        raise ValueError("freshness_seconds must be an integer") from exc


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


def _reject_out_of_order(existing: Metric, incoming_observed_at: str) -> None:
    """Prevent delayed/replayed feeds from replacing newer canonical metric evidence."""
    if not existing.evidence or not existing.evidence.observed_at:
        return
    try:
        current = datetime.fromisoformat(existing.evidence.observed_at.replace("Z", "+00:00"))
        incoming = datetime.fromisoformat(incoming_observed_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if incoming.tzinfo is None:
        incoming = incoming.replace(tzinfo=timezone.utc)
    if incoming.astimezone(timezone.utc) < current.astimezone(timezone.utc):
        raise ValueError("out-of-order business metric evidence rejected")


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
    """Ingest one canonical business metric with explicit source/freshness evidence.

    A metric can only be GREEN when a non-null value is supplied by the authenticated
    feed. Null values are always UNKNOWN. Delayed or future-dated evidence cannot
    overwrite newer canonical evidence. Read-modify-write is atomic per company.
    """
    metric_key = str(metric_key).strip().lower()
    if metric_key not in ALLOWED_METRICS:
        raise ValueError("metric_key must be one of: revenue, pipeline, customers")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source is required")
    observed = _observed_at(observed_at)
    freshness = _freshness(freshness_seconds)
    try:
        truth_state = TruthState(str(state).strip().upper())
    except ValueError as exc:
        raise ValueError("state must be GREEN, DEGRADED, UNKNOWN or STALE") from exc
    if truth_state not in ALLOWED_STATES:
        raise ValueError("invalid metric state")
    normalized = _normalized_value(metric_key, value)
    if normalized is None:
        truth_state = TruthState.UNKNOWN
    spec = ALLOWED_METRICS[metric_key]
    evidence = Evidence(
        source=source.strip()[:300],
        observed_at=observed,
        freshness_seconds=freshness,
        kind="business_metric_feed",
        detail=(detail.strip()[:1000] if isinstance(detail, str) and detail.strip() else "Authenticated canonical business metric feed."),
    )

    def apply(company):
        existing = getattr(company, metric_key)
        _reject_out_of_order(existing, observed)
        metric = Metric(
            key=metric_key,
            label=spec["label"],
            value=normalized,
            unit=(str(unit).strip()[:32] if unit else spec["unit"]),
            state=truth_state,
            evidence=evidence,
        )
        setattr(company, metric_key, metric)
        return metric

    _, metric = mutate_company(company_id, apply)
    append_audit(
        actor="business_metric_feed",
        action="ingest_business_metric",
        level="GREEN",
        company_id=company_id,
        result=f"{metric_key}_ingested_{truth_state.value.lower()}",
        source_data={"metric_key": metric_key, "source": evidence.source, "observed_at": observed, "freshness_seconds": freshness, "state": truth_state.value},
    )
    return metric
