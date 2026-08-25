"""Authenticated HTTP boundary for Opportunity Outcome Capture v0.

The public client boundary records company confirmations only. Official/derived
outcomes are written by trusted in-process adapters so a client cannot label its
own assertion as an official external fact.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from jwt import InvalidTokenError

from api import APP, _db
from account_registry import ensure_account
from auth_context import configured_identity
from opportunity_outcome import (
    OutcomeIdempotencyConflict,
    OutcomeNotFound,
    OutcomeValidationError,
    correct_outcome,
    current_outcome,
    outcome_history,
    record_outcome,
)

bp = Blueprint("opportunity_outcome_api", __name__, url_prefix="/api/v1")


def _identity():
    return configured_identity()


@bp.before_request
def _require_identity():
    if request.method == "OPTIONS":
        return APP.response_class("", status=204, mimetype="text/plain")
    try:
        identity = _identity()
    except (RuntimeError, InvalidTokenError):
        return jsonify({"error": "authentication_required"}), 401
    request.obrasignal_identity = identity
    conn = _db()
    try:
        ensure_account(conn, identity.account_id)
    finally:
        conn.close()
    return None


def _opportunity(conn, opportunity_id):
    return conn.execute(
        "SELECT id, source, external_id FROM tenders WHERE id=?", (opportunity_id,)
    ).fetchone()


def _lot_arg():
    value = request.args.get("lot_id")
    return value.strip() if value and value.strip() else None


def _client_payload():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise OutcomeValidationError("JSON object body required")
    forbidden = {"account_id", "recorded_at", "created_at", "status", "supersedes_outcome_id"}
    supplied = forbidden.intersection(payload)
    if supplied:
        raise OutcomeValidationError(f"client cannot set {sorted(supplied)[0]}")
    if "source_type" in payload and str(payload["source_type"]).upper() != "USER_CONFIRMED":
        raise OutcomeValidationError("client source_type must be USER_CONFIRMED")
    payload.pop("source_type", None)
    return payload


@bp.route("/opportunities/<int:opportunity_id>/outcome", methods=["GET"])
def get_current_outcome(opportunity_id):
    identity = request.obrasignal_identity
    conn = _db()
    try:
        opportunity = _opportunity(conn, opportunity_id)
        if opportunity is None:
            return jsonify({"error": "not_found"}), 404
        item = current_outcome(
            conn,
            identity.account_id,
            opportunity["source"],
            opportunity["external_id"],
            lot_id=_lot_arg(),
        )
        return jsonify({"outcome": item, "account_id": identity.account_id})
    finally:
        conn.close()


@bp.route("/opportunities/<int:opportunity_id>/outcomes", methods=["GET", "POST"])
def outcomes(opportunity_id):
    identity = request.obrasignal_identity
    conn = _db()
    try:
        opportunity = _opportunity(conn, opportunity_id)
        if opportunity is None:
            return jsonify({"error": "not_found"}), 404
        if request.method == "GET":
            items = outcome_history(
                conn,
                identity.account_id,
                opportunity["source"],
                opportunity["external_id"],
                lot_id=_lot_arg(),
            )
            return jsonify({"items": items, "count": len(items), "account_id": identity.account_id})

        payload = _client_payload()
        allowed = {
            "outcome_type", "occurred_at", "lot_id", "decision_id", "award_value",
            "currency", "reason_code", "note", "evidence_refs", "confidence",
            "idempotency_key",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise OutcomeValidationError(f"unsupported field: {sorted(unknown)[0]}")
        item, created = record_outcome(
            conn,
            account_id=identity.account_id,
            source=opportunity["source"],
            external_id=opportunity["external_id"],
            source_type="USER_CONFIRMED",
            **payload,
        )
        return jsonify({"outcome": item, "created": created, "account_id": identity.account_id}), (201 if created else 200)
    except OutcomeIdempotencyConflict as exc:
        return jsonify({"error": "idempotency_conflict", "detail": str(exc)}), 409
    except OutcomeValidationError as exc:
        return jsonify({"error": "invalid_outcome", "detail": str(exc)}), 400
    except OutcomeNotFound:
        return jsonify({"error": "not_found"}), 404
    finally:
        conn.close()


@bp.route("/opportunities/<int:opportunity_id>/outcomes/<outcome_id>", methods=["PATCH"])
def correct(opportunity_id, outcome_id):
    identity = request.obrasignal_identity
    conn = _db()
    try:
        opportunity = _opportunity(conn, opportunity_id)
        if opportunity is None:
            return jsonify({"error": "not_found"}), 404
        existing = conn.execute(
            '''SELECT source, external_id, source_type FROM opportunity_outcomes
               WHERE outcome_id=? AND account_id=?''',
            (outcome_id, identity.account_id),
        ).fetchone()
        if existing is None or existing["source"] != opportunity["source"] or existing["external_id"] != opportunity["external_id"]:
            return jsonify({"error": "not_found"}), 404
        if existing["source_type"] != "USER_CONFIRMED":
            return jsonify({"error": "official_outcome_not_client_editable"}), 403
        payload = _client_payload()
        allowed = {
            "decision_id", "outcome_type", "occurred_at", "award_value", "currency",
            "reason_code", "note", "evidence_refs", "confidence", "idempotency_key",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise OutcomeValidationError(f"unsupported correction field: {sorted(unknown)[0]}")
        item, created = correct_outcome(
            conn,
            account_id=identity.account_id,
            outcome_id=outcome_id,
            source_type="USER_CONFIRMED",
            **payload,
        )
        return jsonify({"outcome": item, "created": created, "account_id": identity.account_id}), (201 if created else 200)
    except OutcomeIdempotencyConflict as exc:
        return jsonify({"error": "idempotency_conflict", "detail": str(exc)}), 409
    except OutcomeValidationError as exc:
        return jsonify({"error": "invalid_outcome", "detail": str(exc)}), 400
    except OutcomeNotFound:
        return jsonify({"error": "not_found"}), 404
    finally:
        conn.close()


if "opportunity_outcome_api" not in APP.blueprints:
    APP.register_blueprint(bp)
