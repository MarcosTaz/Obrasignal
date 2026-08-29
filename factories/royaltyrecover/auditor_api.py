from __future__ import annotations

from flask import Blueprint, jsonify, request

from auditor_handoff import build_formal_audit_packet, packet_to_dict
from repository import RoyaltyRepository


def create_auditor_blueprint(repository: RoyaltyRepository) -> Blueprint:
    bp = Blueprint("royaltyrecover_auditor", __name__)

    @bp.get("/api/v1/findings/<finding_id>/formal-audit-packet")
    def formal_audit_packet(finding_id):
        packet = build_formal_audit_packet(repository, request.royaltyrecover_org_id, finding_id)
        return jsonify(packet_to_dict(packet))

    return bp
