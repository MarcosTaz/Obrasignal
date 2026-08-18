from decision_log import record_decision


def classify(item, is_new, rule_version=None):
    """Return an auditable funnel decision without mutating the tender."""
    score = int(item.get("score") or 0)
    deadline = item.get("deadline")
    features = dict(item.get("decision_features") or {})
    features.update({
        "score": score,
        "has_deadline": bool(deadline),
        "is_new": bool(is_new),
        "market": item.get("market"),
        "source": item.get("source"),
    })

    if not item.get("external_id"):
        return "REJECTED", "MISSING_EXTERNAL_ID", features
    if item.get("hard_capability_blockers"):
        return "REJECTED", "CAPABILITY_BLOCKER", features
    if score < 55:
        return "LOW_SCORE", "SCORE_BELOW_55", features
    if score >= 75:
        return "RELEVANT", "HIGH_COMMERCIAL_SCORE", features
    return "RELEVANT", "COMMERCIAL_SCORE", features


def record_funnel_decision(conn, item, is_new):
    decision, reason, features = classify(item, is_new)
    record_decision(
        conn,
        item.get("source", ""),
        item.get("external_id", ""),
        decision,
        reason,
        item.get("score"),
        features,
    )
    return decision, reason
