from __future__ import annotations

from flask import Blueprint, jsonify, request

from auth_context import configured_identity

from .service import PayloadError, reconcile_payload


def create_earnedcash_blueprint() -> Blueprint:
    bp = Blueprint("earnedcash_api", __name__, url_prefix="/api/v1/earnedcash")

    @bp.get("/health")
    def health():
        identity = configured_identity()
        return jsonify(
            {
                "service": "earnedcash",
                "state": "PILOT_BUILD",
                "tenant_id": identity.account_id,
                "truth_policy": "FAIL_CLOSED",
            }
        )

    @bp.post("/reconcile-ledger")
    def reconcile():
        identity = configured_identity()
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "json_object_required"}), 400
        try:
            result = reconcile_payload(
                payload.get("records"), tenant_id=identity.account_id
            )
        except PayloadError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(result)

    return bp
