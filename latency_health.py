"""Health analysis for pipeline latency telemetry."""


def latency_health(conn, source=None, recent_limit=20, baseline_limit=100):
    """Compare recent stage latency with a historical baseline.

    Returns only observed metrics; no synthetic latency is introduced.
    """
    from latency_metrics import latency_snapshot

    recent = latency_snapshot(conn, source, recent_limit)
    history = latency_snapshot(conn, source, baseline_limit)
    stages = sorted({r["stage"] for r in history})
    out = []
    for stage in stages:
        hist = [r["duration_ms"] for r in history if r["stage"] == stage]
        rec = [r["duration_ms"] for r in recent if r["stage"] == stage]
        if not hist or not rec:
            continue
        hist_avg = sum(hist) / len(hist)
        rec_avg = sum(rec) / len(rec)
        ratio = rec_avg / hist_avg if hist_avg else None
        status = "healthy"
        if ratio is not None and ratio >= 4:
            status = "critical"
        elif ratio is not None and ratio >= 2:
            status = "degraded"
        out.append({
            "stage": stage,
            "recent_samples": len(rec),
            "baseline_samples": len(hist),
            "recent_avg_ms": round(rec_avg, 1),
            "baseline_avg_ms": round(hist_avg, 1),
            "ratio": round(ratio, 2) if ratio is not None else None,
            "status": status,
        })
    return out
