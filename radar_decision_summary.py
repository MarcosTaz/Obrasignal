"""Compact commercial decision summaries for radar cards."""
from __future__ import annotations


def summarize_decision(decision: dict | None) -> dict:
    if not decision:
        return {
            "status": "SEM DECISÃO",
            "class_name": "low",
            "reason": "Ainda não existe uma decisão comercial auditável.",
            "score": None,
            "detail_url": None,
            "rule_version": None,
        }

    status = str(decision.get("decision") or "SEM DECISÃO")
    classes = {
        "QUALIFIED": "hot",
        "RELEVANT": "hot",
        "REVIEW": "good",
        "LOW_SCORE": "low",
        "REJECT": "low",
        "REJECTED": "low",
    }
    reason = str(decision.get("reason") or "Sem razão registada.")
    return {
        "status": status,
        "class_name": classes.get(status, "low"),
        "reason": reason,
        "score": decision.get("score"),
        "rule_version": decision.get("rule_version"),
    }
