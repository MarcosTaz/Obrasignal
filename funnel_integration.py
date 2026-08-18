from opportunity_funnel import record_funnel_decision
from opportunity_match_pipeline import evaluate_row


def persist_and_classify(conn, item, is_new):
    """Persist the normal funnel decision enriched with lot/geography evidence."""
    enriched = dict(item)
    evaluation = evaluate_row(enriched)
    enriched.update({
        "lot_score": evaluation["lot_score"],
        "lot_match": evaluation["match"],
        "lot_id": evaluation["lot_id"],
        "geo_score": evaluation["geography"]["score"],
        "geo_reason": evaluation["geography"]["reason"],
        "decision": evaluation["decision"],
        "match_reason": f"{item.get('match_reason') or ''}; lote={evaluation['lot_score']}/100; {evaluation['geography']['reason']}",
    })
    return record_funnel_decision(conn, enriched, is_new)
