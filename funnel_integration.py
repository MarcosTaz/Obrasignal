from opportunity_funnel import record_funnel_decision
from opportunity_match_pipeline import evaluate_row


def persist_and_classify(conn, item, is_new):
    """Persist the normal funnel decision enriched with full matching evidence."""
    enriched = dict(item)
    evaluation = evaluate_row(enriched)
    enriched.update({
        "lot_score": evaluation["lot_score"],
        "lot_match": evaluation["match"],
        "lot_id": evaluation["lot_id"],
        "geo_score": evaluation["geography"]["score"],
        "geo_reason": evaluation["geography"]["reason"],
        "decision": evaluation["decision"],
        "hard_capability_blockers": evaluation["hard_capability_blockers"],
        "decision_features": {
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
        },
        "match_reason": (
            f"{item.get('match_reason') or ''}; "
            f"lote={evaluation['lot_score']}/100; "
            f"{evaluation['geography']['reason']}; "
            f"economic_fit={evaluation['economic_fit']['status']}"
        ).strip('; '),
    })
    return record_funnel_decision(conn, enriched, is_new)
