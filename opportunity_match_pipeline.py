"""Connect capability, lot matching, economic fit and the decision log."""

from datetime import datetime, timezone

from company_profile import load_profile
from capability_profile import build_capability_profile, capability_matches_text
from decision_log import record_decision
from decision_relevance import derive_relevance
from lot_matcher import match_lot
from economic_fit import evaluate_economic_fit, parse_contract_value
from profile_scoring import personalized_score

RULE_VERSION = "commercial-v2+lot-v1+capability-v2+economic-fit-v3"


def _cpv_evidence(lot, capability):
    """Separate broad CPV-family hints from specific commercial evidence."""
    codes = [part.strip() for part in str(lot.get("cpv") or "").split("|") if part.strip()]
    prefixes = [str(value).strip() for value in capability.get("cpv_prefixes", []) if str(value).strip()]
    matches = [(code, prefix) for code in codes for prefix in prefixes if code.startswith(prefix)]
    if not matches:
        return {"status": "UNKNOWN", "strength": "NONE", "matched_prefixes": [],
                "reason": "sem correspondência CPV com o perfil"}
    matched_prefixes = sorted({prefix for _, prefix in matches}, key=lambda value: (-len(value), value))
    # Two-digit divisions (45, 44, 42, 43) contain many unrelated trades.
    # They are useful for recall, but are not proof that this company performs
    # the work. Four or more digits identify a materially narrower group/class.
    specific = any(len(prefix) >= 4 for prefix in matched_prefixes)
    return {
        "status": "MATCH" if specific else "PARTIAL",
        "strength": "STRONG" if specific else "WEAK",
        "matched_prefixes": matched_prefixes,
        "reason": ("CPV específico compatível" if specific else "apenas família CPV genérica compatível"),
    }


def _lot_from_row(row):
    return {
        "lot_id": row.get("external_id") or row.get("id"),
        "title": row.get("title"),
        "description": row.get("description"),
        "buyer": row.get("buyer"),
        "country": row.get("country"),
        "cpv": row.get("cpv"),
        "value": row.get("value"),
        "value_numeric": row.get("value_numeric") or parse_contract_value(row.get("value")),
        "deadline": row.get("deadline"),
        "procedure_type": row.get("procedure_type") or row.get("notice_type"),
        "locations": row.get("locations") or [{"country": row.get("country")}],
    }


def _hard_capability_checks(lot, capability):
    """Return deterministic blockers; missing data stays UNKNOWN, not PASS."""
    blockers = []
    deadline = lot.get("deadline")
    if deadline:
        try:
            parsed = datetime.fromisoformat(str(deadline).strip().replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if parsed.astimezone(timezone.utc) < datetime.now(timezone.utc):
                blockers.append("prazo de apresentação terminado")
        except (TypeError, ValueError):
            # An invalid deadline remains UNKNOWN rather than being guessed.
            pass
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


def _explain_evaluation(profile_score, lot_score, geo, capability_evidence, cpv_evidence, economics, hard_blockers):
    """Return structured evidence for UI/API while preserving the decision model."""
    factors = [
        {"key": "profile", "label": "Perfil comercial", "score": profile_score, "reason": "Compatibilidade com o perfil da empresa"},
        {"key": "lot", "label": "Lote", "score": lot_score, "reason": "Compatibilidade do lote"},
        {"key": "geography", "label": "Geografia", "score": None, "reason": geo.get("reason") or "Geografia não determinada"},
        {"key": "capability", "label": "Capacidade", "score": None, "reason": capability_evidence.get("reason") or "Capacidade não determinada"},
        {"key": "cpv", "label": "CPV", "score": None, "reason": cpv_evidence["reason"]},
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
    cpv_evidence = _cpv_evidence(lot, capability)
    hard_blockers = _hard_capability_checks(lot, capability)
    countries = {str(value).strip().upper() for value in capability.get("countries", []) if str(value).strip()}
    country = str(lot.get("country") or "").strip().upper()
    if countries and country and country not in countries:
        hard_blockers.append("país fora da cobertura da empresa")
    result = match_lot(lot, profile)
    # Use the normalized capability values at the economic boundary. This is
    # the same object exposed in decision features and prevents legacy aliases
    # or numeric strings from disappearing between profile and matcher.
    economic_profile = {**profile, "min_value": capability.get("min_value"), "max_value": capability.get("max_value")}
    economics = evaluate_economic_fit(
        lot.get("value_numeric") or lot.get("value"),
        economic_profile,
        opportunity=lot,
    )
    failed_economic_rules = {rule["rule"] for rule in economics.get("rules", []) if not rule.get("passed")}
    if "min_value" in failed_economic_rules and "valor abaixo do mínimo da empresa" not in hard_blockers:
        hard_blockers.append("valor abaixo do mínimo da empresa")
    if "max_value" in failed_economic_rules and "valor acima do máximo da empresa" not in hard_blockers:
        hard_blockers.append("valor acima do máximo da empresa")
    if result["geography"].get("reason") == "região fora do perfil":
        hard_blockers.append("região fora da cobertura da empresa")

    # The source `tenders.score` field is legacy presentation state from the
    # original root application. The canonical product score is produced by
    # commercial-v2 inside match_lot(). Never let stale source scoring alter
    # the account-specific decision pipeline.
    global_score = result["commercial"]["score"]
    profile_score = personalized_score(source_row, base_score=global_score, profile=profile)[0]
    positive_commercial_evidence = capability_evidence["matched"] or cpv_evidence["strength"] == "STRONG"
    # Country, an in-range value and a broad CPV division improve recall, but
    # cannot establish high relevance by themselves.
    if not positive_commercial_evidence:
        profile_score = min(profile_score, 59)
    # A score shown to a customer must agree with deterministic eligibility
    # rules. Previously a CPV/value/deadline blocker could say REJECT while
    # the same card still displayed e.g. 90/100.
    if hard_blockers:
        profile_score = min(profile_score, 35)
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

    # Relevance is deliberately orthogonal to the action label. Broad geography,
    # value and generic lot attractiveness cannot turn REVIEW into relevance.
    relevance = derive_relevance(capability_evidence, cpv_evidence, hard_blockers)
    relevant_shortlist_eligible = relevance["state"] == "RELEVANT" and not hard_blockers

    reason = (
        f"perfil={profile_score}; lote={lot_score}; geografia={geo['reason']}; "
        f"capacidade={capability_evidence['reason']}; "
        f"cpv={cpv_evidence['reason']}; "
        f"economic_fit={economics['status']}; {economics['reason']}"
    )
    if hard_blockers:
        reason += "; bloqueios=" + ", ".join(hard_blockers)

    explanation = _explain_evaluation(profile_score, lot_score, geo, capability_evidence, cpv_evidence, economics, hard_blockers)

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
        "cpv_evidence": cpv_evidence,
        "hard_capability_blockers": hard_blockers,
        "relevance": relevance,
        "relevant_shortlist_eligible": relevant_shortlist_eligible,
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
            "cpv_evidence": evaluation["cpv_evidence"],
            "hard_capability_blockers": evaluation["hard_capability_blockers"],
            "relevance": evaluation["relevance"],
            "relevant_shortlist_eligible": evaluation["relevant_shortlist_eligible"],
            "explanation": evaluation["explanation"],
        },
        rule_version=RULE_VERSION,
        account_id=account_id,
    )
    # Real normalized market data has reached the account-specific decision path.
    # Only explicit relevance eligibility may establish a relevant shortlist.
    try:
        from account_registry import ensure_account
        from evaluation_policy import record_evaluation_event
        ensure_account(conn, account_id)
        record_evaluation_event(conn, account_id, 'market_data_available', metadata={'source': row.get('source')})
        if evaluation['relevant_shortlist_eligible']:
            record_evaluation_event(conn, account_id, 'first_shortlist_generated', metadata={
                'source': row.get('source'),
                'external_id': row.get('external_id') or str(row.get('id')),
                'relevance_state': evaluation['relevance']['state'],
                'relevance_rule_version': evaluation['relevance']['rule_version'],
            })
    except Exception:
        # Decisioning remains primary; evaluation telemetry must degrade gracefully.
        pass
    return evaluation
