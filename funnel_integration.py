from decision_log import record_decision
from opportunity_match_pipeline import evaluate_row


def persist_and_classify(conn, item, is_new, account_id='default'):
    """Persist the canonical commercial decision with full audit evidence."""
    enriched = dict(item)
    evaluation = evaluate_row(enriched)
    enriched.update({
        "lot_score": evaluation["lot_score"],
        "lot_match": evaluation["match"],
        "lot_id": evaluation["lot_id"],
        "geo_score": evaluation["geography"]["score"],
        "geo_reason": evaluation["geography"]["reason"],
        "decision": evaluation["decision"],
        "match_reason": evaluation["reason"],
    })

    features = {
        "profile_score": evaluation["profile_score"],
        "lot_score": evaluation["lot_score"],
        "lot_id": evaluation["lot_id"],
        "match": evaluation["match"],
        "geography": evaluation["geography"],
        "commercial": evaluation["commercial"],
        "economic_fit": evaluation["economic_fit"],
        "capability": evaluation["capability"],
        "capability_evidence": evaluation["capability_evidence"],
        "hard_capability_blockers": evaluation["hard_capability_blockers"],
        "explanation": evaluation["explanation"],
    }

    record_decision(
        conn,
        enriched.get("source", ""),
        enriched.get("external_id", ""),
        evaluation["decision"],
        evaluation["reason"],
        score=evaluation["profile_score"],
        features=features,
        rule_version="commercial-v2+lot-v1+capability-v1+economic-fit-v2",
        account_id=account_id,
    )
    return evaluation["decision"], evaluation["reason"]
