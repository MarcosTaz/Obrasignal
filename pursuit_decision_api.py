"""Authenticated HTTP contract for the Opportunity Pursuit Decision Journal v0."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from jwt import InvalidTokenError

from api import APP, _apply_cors, _db, _iso_now
from auth_context import configured_identity
from pursuit_decision import (
    DecisionValidationError,
    IdempotencyConflict,
    current_decision,
    decision_history,
    record_pursuit_decision,
)
from pursuit_decision_presentation import present_pursuit_decision

bp = Blueprint("pursuit_decision_api", __name__, url_prefix="/api/v1")


def _identity():
    existing = getattr(request, "obrasignal_identity", None)
    return existing if existing is not None else configured_identity()


@bp.before_request
def _require_identity():
    if request.method == "OPTIONS":
        return _headers(APP.response_class("", status=204, mimetype="text/plain"))
    try:
        request.obrasignal_identity = _identity()
    except (RuntimeError, InvalidTokenError):
        return jsonify({"error": "authentication_required"}), 401
    return None


@bp.after_request
def _headers(response):
    response = _apply_cors(response)
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-ObraSignal-Version, Authorization, Idempotency-Key"
    return response


def _opportunity(conn, opportunity_id):
    return conn.execute(
        '''SELECT id, source, external_id, title, deadline, publication_date, last_seen, score
           FROM tenders WHERE id=?''',
        (int(opportunity_id),),
    ).fetchone()


def _snapshot(row):
    return {field: row[field] for field in (
        "source", "external_id", "title", "deadline", "publication_date", "last_seen", "score"
    )}


def _revision_ref(row):
    observed = row["last_seen"] or row["publication_date"] or "unknown"
    return f'{row["source"]}:{row["external_id"]}:{observed}'


@bp.route("/opportunities/<int:opportunity_id>/decision", methods=["GET", "POST"])
def opportunity_decision(opportunity_id):
    identity = request.obrasignal_identity
    conn = _db()
    try:
        opportunity = _opportunity(conn, opportunity_id)
        if opportunity is None:
            return jsonify({"error": "not_found"}), 404
        if request.method == "GET":
            current = current_decision(conn, identity.account_id, opportunity_id)
            history = decision_history(conn, identity.account_id, opportunity_id)
            return jsonify({
                "decision": current,
                "presentation": present_pursuit_decision(current, history),
                "account_id": identity.account_id,
                "generated_at": _iso_now(),
            })

        payload = request.get_json(silent=True) or {}
        requested_actor_type = str(payload.get("actor_type") or "HUMAN").strip().upper()
        if requested_actor_type != "HUMAN":
            return jsonify({
                "error": "invalid_decision",
                "detail": "actor_type is server-controlled on the human decision API",
            }), 400
        idempotency_key = request.headers.get("Idempotency-Key") or payload.get("idempotency_key")
        actor_id = identity.subject if getattr(identity, "subject", None) else payload.get("actor_id")
        decision, created = record_pursuit_decision(
            conn,
            account_id=identity.account_id,
            opportunity_id=opportunity_id,
            decision_type=payload.get("decision_type", payload.get("decision")),
            reason_codes=payload.get("reason_codes"),
            freeform_note=payload.get("freeform_note", payload.get("note")),
            blockers=payload.get("blockers"),
            unknowns=payload.get("unknowns"),
            readiness_ref=payload.get("readiness_ref"),
            evidence_refs=payload.get("evidence_refs"),
            opportunity_revision_ref=payload.get("opportunity_revision_ref") or _revision_ref(opportunity),
            opportunity_state=_snapshot(opportunity),
            confidence=payload.get("confidence"),
            actor_id=actor_id,
            actor_type="HUMAN",
            decided_at=payload.get("decided_at"),
            idempotency_key=idempotency_key,
        )
        return jsonify({
            "ok": True,
            "created": created,
            "decision": decision,
            "account_id": identity.account_id,
            "generated_at": _iso_now(),
        }), 201 if created else 200
    except DecisionValidationError as exc:
        return jsonify({"error": "invalid_decision", "detail": str(exc)}), 400
    except IdempotencyConflict as exc:
        return jsonify({"error": "idempotency_conflict", "detail": str(exc)}), 409
    finally:
        conn.close()


@bp.route("/opportunities/<int:opportunity_id>/decisions", methods=["GET"])
def opportunity_decision_history(opportunity_id):
    identity = request.obrasignal_identity
    conn = _db()
    try:
        if _opportunity(conn, opportunity_id) is None:
            return jsonify({"error": "not_found"}), 404
        history = decision_history(conn, identity.account_id, opportunity_id)
        return jsonify({
            "items": history,
            "count": len(history),
            "account_id": identity.account_id,
            "generated_at": _iso_now(),
        })
    finally:
        conn.close()


if "pursuit_decision_api" not in APP.blueprints:
    APP.register_blueprint(bp)
