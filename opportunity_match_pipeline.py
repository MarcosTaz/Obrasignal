"""Connect opportunity rows to lot matching, economic fit and the decision log."""

from company_profile import load_profile
from decision_log import record_decision
from lot_matcher import match_lot
from economic_fit import evaluate_economic_fit

RULE_VERSION = "commercial-v2+lot-v1+economic-fit-v2"


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


def evaluate_row(row, profile=None):
    profile = profile or load_profile()
    source_row = dict(row)
    lot = _lot_from_row(source_row)
    result = match_lot(lot, profile)
    economics = evaluate_economic_fit(
        lot.get("value_numeric") or lot.get("value"),
        profile,
        opportunity=lot,
    )
    profile_score = int(source_row.get("profile_score") or source_row.get("score") or 0)
    lot_score = int(result["score"])
    geo = result["geography"]

    if profile_score >= 75 and lot_score >= 65 and economics["status"] in ("FAVOURABLE", "REVIEW"):
        decision = "QUALIFIED"
    elif profile_score >= 60 or lot_score >= 65:
        decision = "REVIEW"
    else:
        decision = "REJECT"

    reason = (
        f"perfil={profile_score}; lote={lot_score}; geografia={geo['reason']}; "
        f"economic_fit={economics['status']}; {economics['reason']}"
    )
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
    }


def evaluate_and_record(conn, row, profile=None):
    evaluation = evaluate_row(row, profile)
    record_decision(
        conn,
        row.get("source") or "UNKNOWN",
        row.get("external_id") or str(row.get("id")),
        evaluation["decision"],
        evaluation["reason"],
        score=evaluation["profile_score"],
        features={
            "lot_score": evaluation["lot_score"],
            "lot_id": evaluation["lot_id"],
            "match": evaluation["match"],
            "geography": evaluation["geography"],
            "commercial": evaluation["commercial"],
            "economic_fit": evaluation["economic_fit"],
        },
        rule_version=RULE_VERSION,
    )
    return evaluation
