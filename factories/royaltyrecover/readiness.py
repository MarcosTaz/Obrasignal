from __future__ import annotations

from flask import Blueprint, jsonify, request

from repository import RoyaltyRepository


def create_readiness_blueprint(repository: RoyaltyRepository) -> Blueprint:
    bp = Blueprint("royaltyrecover_readiness", __name__)

    @bp.get("/api/v1/readiness")
    def readiness():
        status = repository.integrity_status()
        response = {
            "ready": bool(status["ready"]),
            "database_integrity": status["integrity"],
            "foreign_key_violation_count": status["foreign_key_violation_count"],
            "journal_mode": status["journal_mode"],
            "busy_timeout_ms": status["busy_timeout_ms"],
            "organization_id": request.royaltyrecover_org_id,
            "claim_generation": False,
        }
        return jsonify(response), 200 if response["ready"] else 503

    return bp
