"""Connect capability, lot matching, economic fit and the decision log."""

from company_profile import load_profile
from capability_profile import build_capability_profile, capability_matches_text
from decision_log import record_decision
from lot_matcher import match_lot
from economic_fit import evaluate_economic_fit
from profile_scoring import personalized_score

RULE_VERSION = "commercial-v2+lot-v1+capability-v1+economic-fit-v2"


def _lot_from_row(row):
    return {
        "lot_id": row.get("external_id") or row.get("id"),
        "title": row.get("title"),
        "description": row.get("description"),
        "buyer": row.get("buyer"),
        "country": row.get("country"),
        "cpv": row.get("cpv"),
        "value": row.get("value"),
        "value_numeric": row.get("value_numeric"),
        "deadline": row.get("deadline"),
        "procedure_type": row.get("procedure_type") or row.get("notice_type"),
        "locations": row.get("locations") or [{"country": row.get("country")}],
    }


def _hard_capability_checks(lot, capability):
    """Return deterministic blockers; missing data stays UNKNOWN, not PASS."""
    blockers = []
    amount = lot.get("value_numeric")
    try:
        amount = float(amount) if amount not in (None, "") else None
    except (TypeError, ValueError):
        amount = None

    if amount is not None:
        if capability.get("min_value") is not None and amount < float(capability["min_value"]):
            blockers.append("valor abaixo do mínimo da empresa")
        if capability.get("max_value") is not None and amount > float(capability["max_value"]):
            blockers.append("valor acima do máximo da empresa")

    procedure = str(lot.get("procedure_type") or "").strip().upper()
    excluded = {str(v).strip().upper() for v in capability.get("excluded_procedure_types", [])}
    if procedure and procedure in excluded:
        blockers.append(f"procedimento excluído: {procedure}")

    cpv = str(lot.get("cpv") or "")
    prefixes = [str(v).strip() for v in capability.get("cpv_prefixes", []) if str(v).strip()]
    if cpv and prefixes:
        codes = [part.strip() for part in cpv.split("|") if part.strip()]
        if codes and not any(any(code.startswith(prefix) for prefix in prefixes) for code in codes):
            blockers.append("CPV fora das famílias aceites pela empresa")

    text = " ".join(str(v) for v in (lot.get("title"), lot.get("description")) if v)
    text_folded = text.casefold()
    for exclusion in capability.get("hard_exclusions", []):
        term = str(exclusion).strip()
        if term and term.casefold() in text_folded:
            blockers.append(f"exclusão da empresa encontrada: {term}")

    return blockers


def _explain_evaluation(profile_score, lot_score, geo, capability_evidence, economics, hard_blockers):
    """Return structured evidence for UI/API while preserving the decision model."""
    factors = [
        {"key": "profile", "label": "Perfil comercial", "score": profile_score, "reason": "Compatibilidade com o perfil da empresa"},
        {"key": "lot", "label": "Lote", "score": lot_score, "reason": "Compatibilidade do lote"},
        {"key": "geography", "label": "Geografia", "score": None, "reason": geo.get("reason") or "Geografia não determinada"},
        {"key": "capability", "label": "Capacidade", "score": None, "reason": capability_evidence.get("reason") or "Capacidade não determinada"},
        {"key": "economic_fit", "label": "Economic Fit", "score": economics.get("score"), "reason": economics.get("reason") or economics.get("status")},
    ]
    negatives = [{"key": "blocker", "label": "Bloqueio", "reason": blocker} for blocker in hard_blockers]
    return {"factors": factors, "negative_factors": negatives}


def evaluate_row(row, profile=None):
    profile = profile or load_profile()
    source_row = dict(row)
    lot = _lot_from_row(source_row)
    capability = build_capability_profile(profile)
    capability_evidence = capability_matches_text(
        capability,
        " ".join(str(v) for v in (lot.get("title"), lot.get("description")) if v),
    )
    hard_blockers = _hard_capability_checks(lot, capability)
    result = match_lot(lot, profile)
    economics = evaluate_economic_fit(
        lot.get("value_numeric") or lot.get("value"),
        profile,
        opportunity=lot,
    )

    # The source `tenders.score` field is legacy presentation state from the
    # original root application. The canonical product score is produced by
    # commercial-v2 inside match_lot(). Never let stale source scoring alter
    # the account-specific decision pipeline.
    global_score = result["commercial"]["score"]
    profile_score = personalized_score(source_row, base_score=global_score, profile=profile)[0]
    lot_score = int(result["score"])
    geo = result["geography"]

    if hard_blockers:
        decision = "REJECT"
    elif profile_score >= 75 and lot_score >= 65 and economics["status"] in ("FAVOURABLE", "REVIEW"):
        decision = "QUALIFIED"
    elif profile_score >= 60 or lot_score >= 65:
        decision = "REVIEW"
    else:
        decision = "REJECT"

    reason = (
        f"perfil={profile_score}; lote={lot_score}; geografia={geo['reason']}; "
        f"capacidade={capability_evidence['reason']}; "
        f"economic_fit={economics['status']}; {economics['reason']}"
    )
    if hard_blockers:
        reason += "; bloqueios=" + ", ".join(hard_blockers)

    explanation = _explain_evaluation(profile_score, lot_score, geo, capability_evidence, economics, hard_blockers)

    return {
        "decision": decision,
        "reason": reason,
        "profile_score": profile_score,
        "lot_score": lot_score,
        "lot_id": result.get("lot_id"),
        "match": result.get("match"),
        "geography": geo,
        "commercial": result.get("commercial"),
        "economic_fit": economics,
        "capability": capability,
        "capability_evidence": capability_evidence,
        "hard_capability_blockers": hard_blockers,
        "explanation": explanation,
    }


def evaluate_and_record(conn, row, profile=None, account_id="default"):
    evaluation = evaluate_row(row, profile)
    record_decision(
        conn,
        row.get("source") or "UNKNOWN",
        row.get("external_id") or str(row.get("id")),
        evaluation["decision"],
        evaluation["reason"],
        score=evaluation["profile_score"],
        features={
            "profile_score": evaluation["profile_score"],
            "lot_score": evaluation["lot_score"],
            "lot_id": evaluation["lot_id"],
            "match": evaluation["match"],
            "geography": evaluation["geography"],
            "commercial": evaluation["commercial"],
            "economic_fit": evaluation["economic_fit"],
            "capability_evidence": evaluation["capability_evidence"],
            "hard_capability_blockers": evaluation["hard_capability_blockers"],
            "explanation": evaluation["explanation"],
        },
        rule_version=RULE_VERSION,
        account_id=account_id,
    )
    return evaluation
