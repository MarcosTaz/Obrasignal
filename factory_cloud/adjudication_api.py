from __future__ import annotations

from typing import Callable

from flask import Flask, jsonify, request

from factory_cloud.finding_adjudication import FindingAdjudication, FindingAdjudicationError, FindingAdjudicationLedger
from factory_cloud.shared_contracts import SharedContractError

ADJUDICATION_API_ERRORS = (KeyError, TypeError, ValueError, SharedContractError, FindingAdjudicationError)


def _public(decision: FindingAdjudication) -> dict:
    return {
        "finding_id": decision.finding_id,
        "vertical": decision.vertical,
        "entitlement_state": decision.entitlement_state,
        "breach_state": decision.breach_state,
        "actionable": decision.actionable,
        "adjudicated_at": decision.adjudicated_at,
        "decision_evidence_present": decision.decision_evidence_hash is not None,
    }


def register_adjudication_api(
    app: Flask,
    *,
    ledger: FindingAdjudicationLedger,
    identity: Callable[[], tuple[str, str]],
) -> None:
    @app.get("/findings/<finding_id>/adjudication")
    def adjudication_get(finding_id: str):
        try:
            tenant_id, _actor_id = identity()
            return jsonify(_public(ledger.get(tenant_id=tenant_id, finding_id=finding_id)))
        except ADJUDICATION_API_ERRORS as exc:
            message = str(exc)
            status = 404 if message == "tenant-scoped adjudication not found" else 422
            return jsonify({"error": type(exc).__name__, "message": message}), status

    @app.post("/findings/<finding_id>/adjudicate")
    def adjudication_post(finding_id: str):
        try:
            tenant_id, actor_id = identity()
            payload = request.get_json(force=True) or {}
            breach = payload.get("breach_established")
            if breach is not None and not isinstance(breach, bool):
                raise FindingAdjudicationError("breach_established must be boolean or omitted")
            decision = ledger.adjudicate(
                tenant_id=tenant_id,
                finding_id=finding_id,
                adjudicator=actor_id,
                entitlement_established=payload["entitlement_established"],
                breach_established=breach,
                evidence_ref=str(payload["evidence_ref"]),
                reason=str(payload["reason"]),
            )
            return jsonify(_public(decision))
        except ADJUDICATION_API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422
