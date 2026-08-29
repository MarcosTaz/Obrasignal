from company_profile import load_profile
from decision_log import record_decision
from opportunity_match_pipeline import RULE_VERSION, evaluate_row


_UNUSABLE_EVALUATION_SOURCES = {"", "UNKNOWN", "UNAVAILABLE", "ERROR"}


def _record_customer_evaluation_events(conn, item, evaluation, account_id):
    """Bridge the real account-scoped classification path into Evaluation.

    A persisted decision proves usable market data only when the normalized row
    has a concrete source identity and opportunity identity. A first relevant
    shortlist is emitted only from explicit, versioned relevance eligibility;
    QUALIFIED/REVIEW labels never imply relevance.
    """
    source = str(item.get("source") or "").strip()
    external_id = str(item.get("external_id") or item.get("id") or "").strip()
    if source.upper() in _UNUSABLE_EVALUATION_SOURCES or not external_id:
        return False

    from account_registry import ensure_account
    from evaluation_policy import record_evaluation_event

    ensure_account(conn, account_id)
    record_evaluation_event(
        conn,
        account_id,
        "market_data_available",
        metadata={"source": source, "external_id": external_id},
    )
    if evaluation.get("relevant_shortlist_eligible") is True:
        relevance = evaluation.get("relevance") if isinstance(evaluation.get("relevance"), dict) else {}
        record_evaluation_event(
            conn,
            account_id,
            "first_shortlist_generated",
            metadata={
                "source": source,
                "external_id": external_id,
                "relevance_state": relevance.get("state"),
                "relevance_rule_version": relevance.get("rule_version"),
            },
        )
    return True


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
        "relevance": evaluation["relevance"],
        "relevant_shortlist_eligible": evaluation["relevant_shortlist_eligible"],
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
        rule_version=RULE_VERSION,
        account_id=account_id,
    )

    try:
        _record_customer_evaluation_events(conn, enriched, evaluation, account_id)
    except Exception:
        pass
    return evaluation["decision"], evaluation["reason"]
