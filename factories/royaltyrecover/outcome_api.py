from __future__ import annotations

from flask import Blueprint, jsonify, request

from authz import role_allows
from outcome_store import OutcomeStore
from repository import RoyaltyRepository


def create_outcome_blueprint(repository: RoyaltyRepository) -> Blueprint:
    bp = Blueprint("royaltyrecover_outcomes", __name__)
    outcomes = OutcomeStore(repository)

    def org_id():
        return request.royaltyrecover_org_id

    def actor_id():
        return request.royaltyrecover_actor_id

    def require_reviewer():
        if not role_allows(request.royaltyrecover_role, "REVIEWER"):
            return jsonify({"error": "insufficient_role", "required_role": "REVIEWER"}), 403
        return None

    def payload():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError("JSON object required")
        return data

    @bp.post("/api/v1/payments")
    def record_payment():
        try:
            data = payload()
            item = outcomes.record_payment(
                org_id(), str(data.get("agreement_id") or ""), str(data.get("payment_date") or ""),
                str(data.get("currency") or ""), data.get("amount"), str(data.get("evidence_id") or ""), actor_id(),
                payment_reference=data.get("payment_reference"),
            )
        except ValueError as exc:
            return jsonify({"error": "invalid_input", "detail": str(exc)}), 400
        return jsonify({"payment": item}), 201

    @bp.post("/api/v1/findings/<finding_id>/outcomes")
    def record_outcome(finding_id):
        denied = require_reviewer()
        if denied:
            return denied
        try:
            data = payload()
            item = outcomes.record_outcome(
                org_id(), finding_id, str(data.get("outcome_type") or ""), actor_id(),
                evidence_id=data.get("evidence_id"), notes=data.get("notes"), resolved_at=data.get("resolved_at"),
            )
        except ValueError as exc:
            return jsonify({"error": "invalid_input", "detail": str(exc)}), 400
        return jsonify({"outcome": item}), 201

    @bp.post("/api/v1/outcomes/<outcome_id>/recovered-amounts")
    def record_recovered_amount(outcome_id):
        denied = require_reviewer()
        if denied:
            return denied
        try:
            data = payload()
            item = outcomes.record_recovered_amount_candidate(
                org_id(), outcome_id, str(data.get("payment_id") or ""), data.get("amount"),
                str(data.get("currency") or ""), str(data.get("evidence_id") or ""), actor_id(),
            )
        except ValueError as exc:
            return jsonify({"error": "invalid_input", "detail": str(exc)}), 400
        return jsonify({"recovered_amount": item, "verified": False}), 201

    @bp.post("/api/v1/recovered-amounts/<recovered_id>/verify")
    def verify_recovered_amount(recovered_id):
        denied = require_reviewer()
        if denied:
            return denied
        try:
            data = payload()
            item = outcomes.verify_recovered_amount(org_id(), recovered_id, actor_id(), str(data.get("rationale") or ""))
        except ValueError as exc:
            return jsonify({"error": "invalid_input", "detail": str(exc)}), 400
        return jsonify({"recovered_amount": item, "verified": True}), 200

    @bp.get("/api/v1/recoveries/verified-summary")
    def verified_summary():
        return jsonify(outcomes.verified_summary(org_id()))

    return bp
