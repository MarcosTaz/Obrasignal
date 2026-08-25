from datetime import datetime, timezone

from company_profile import load_profile
from decision_evidence import maybe_decision_evidence
from decision_log import record_decision
from opportunity_match_pipeline import RULE_VERSION, evaluate_row


def persist_and_classify(conn, item, is_new, account_id='default'):
    """Persist the canonical commercial decision with full account-scoped evidence."""
    enriched = dict(item)
    profile = load_profile(account_id)
    evaluation = evaluate_row(enriched, profile=profile)
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
        "cpv_evidence": evaluation["cpv_evidence"],
        "hard_capability_blockers": evaluation["hard_capability_blockers"],
        "explanation": evaluation["explanation"],
    }

    decided_at = datetime.now(timezone.utc).isoformat()
    evidence = maybe_decision_evidence(
        account_id,
        enriched,
        profile,
        evaluation,
        rule_version=RULE_VERSION,
        decided_at=decided_at,
    )
    if evidence is not None:
        features["decision_evidence"] = evidence

    record_decision(
        conn,
        enriched.get("source", ""),
        enriched.get("external_id", ""),
        evaluation["decision"],
        evaluation["reason"],
        score=evaluation["profile_score"],
        features=features,
        rule_version=RULE_VERSION,
        decided_at=decided_at,
        account_id=account_id,
    )
    return evaluation["decision"], evaluation["reason"]
