from __future__ import annotations

import hmac
import os
from functools import wraps

from flask import Blueprint, jsonify, request

from .business_feed import ingest_business_metric, ingest_operational_metric
from .registry import append_audit
from .security import secret_is_usable

business_api = Blueprint("business_api", __name__)


def metric_ingest_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        expected = os.getenv("FCC_METRIC_INGEST_TOKEN")
        if not secret_is_usable(expected, 16):
            return jsonify({"ok": False, "error": "metric_ingest_not_configured"}), 503
        header = request.headers.get("Authorization", "")
        prefix = "Bearer "
        candidate = header[len(prefix):] if header.startswith(prefix) else ""
        if not candidate or not hmac.compare_digest(candidate, expected):
            return jsonify({"ok": False, "error": "metric_ingest_authentication_required"}), 401
        return fn(*args, **kwargs)
    return wrapped


def _request_object() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _metric_json(metric):
    return metric.__dict__ | {"state": metric.state.value, "evidence": metric.evidence.__dict__ if metric.evidence else None}


def _audit_rejection(action: str, data: dict, exc: Exception) -> None:
    append_audit(
        actor="metric_feed",
        action=action,
        level="GREEN",
        company_id=str(data.get("company_id", ""))[:120] or None,
        result=f"rejected_invalid_{action}",
        source_data={
            "metric_key": str(data.get("metric_key", ""))[:120],
            "source_present": isinstance(data.get("source"), str) and bool(data.get("source", "").strip()),
            "payload_keys": sorted(str(key)[:120] for key in data.keys())[:50],
        },
        failure_state=str(exc)[:300],
    )


@business_api.post("/api/ingest/business-metric")
@metric_ingest_required
def api_ingest_business_metric():
    data = _request_object()
    try:
        metric = ingest_business_metric(
            company_id=str(data.get("company_id", "")),
            metric_key=str(data.get("metric_key", "")),
            value=data.get("value"),
            source=data.get("source"),
            observed_at=data.get("observed_at"),
            freshness_seconds=data.get("freshness_seconds", 3600),
            state=str(data.get("state", "GREEN")),
            unit=data.get("unit"),
            detail=data.get("detail"),
        )
    except (TypeError, ValueError) as exc:
        _audit_rejection("business_metric", data, exc)
        return jsonify({"ok": False, "error": "invalid_business_metric", "detail": str(exc)}), 400
    return jsonify({"ok": True, "company_id": str(data.get("company_id", "")), "metric": _metric_json(metric)}), 200


@business_api.post("/api/ingest/metric")
@metric_ingest_required
def api_ingest_operational_metric():
    data = _request_object()
    try:
        metric = ingest_operational_metric(
            company_id=str(data.get("company_id", "")),
            metric_key=str(data.get("metric_key", "")),
            label=data.get("label"),
            value=data.get("value"),
            source=data.get("source"),
            observed_at=data.get("observed_at"),
            freshness_seconds=data.get("freshness_seconds", 3600),
            state=str(data.get("state", "GREEN")),
            unit=data.get("unit"),
            detail=data.get("detail"),
        )
    except (TypeError, ValueError) as exc:
        _audit_rejection("operational_metric", data, exc)
        return jsonify({"ok": False, "error": "invalid_operational_metric", "detail": str(exc)}), 400
    return jsonify({"ok": True, "company_id": str(data.get("company_id", "")), "metric": _metric_json(metric)}), 200
