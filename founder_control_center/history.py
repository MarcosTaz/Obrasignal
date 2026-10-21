from __future__ import annotations

from .registry import list_company_history


def _metric_projection(metric: dict) -> dict:
    evidence = metric.get("evidence") or {}
    return {
        "value": metric.get("value"),
        "unit": metric.get("unit"),
        "state": metric.get("state", "UNKNOWN"),
        "source": evidence.get("source", "UNKNOWN"),
        "observed_at": evidence.get("observed_at"),
        "freshness_seconds": evidence.get("freshness_seconds"),
        "kind": evidence.get("kind", "unknown"),
    }


def safe_company_history(company_id: str, limit: int = 50) -> list[dict]:
    """Return decision-useful history without replaying arbitrary evidence detail or URLs."""
    items = list_company_history(company_id, limit)
    safe = []
    for item in items:
        safe.append({
            "captured_at": item.get("captured_at"),
            "status": item.get("status", "UNKNOWN"),
            "stage": item.get("stage", "UNKNOWN"),
            "active": item.get("active", "UNKNOWN"),
            "next": item.get("next", "UNKNOWN"),
            "wait": item.get("wait", "NONE"),
            "revenue": _metric_projection(item.get("revenue") or {}),
            "pipeline": _metric_projection(item.get("pipeline") or {}),
            "customers": _metric_projection(item.get("customers") or {}),
            "repository": {
                "commit": (item.get("repository") or {}).get("commit"),
                "ci": (item.get("repository") or {}).get("ci", "UNKNOWN"),
            },
            "application": {
                "deployment": (item.get("application") or {}).get("deployment", "UNKNOWN"),
                "health": (item.get("application") or {}).get("health", "UNKNOWN"),
            },
            "factory_feed_freshness": list(item.get("factory_feed_freshness") or []),
        })
    return safe
