from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from flask import jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from authz import role_allows
from production_repository import ProductionRoyaltyRepository
from production_security import load_production_config, readiness_snapshot
from web_app import create_app


CONFIG = load_production_config()
RAW_CREDENTIALS = json.loads(os.environ["ROYALTYRECOVER_CREDENTIALS_JSON"])
REPOSITORY = ProductionRoyaltyRepository.file(CONFIG.db_path, audit_secret=CONFIG.audit_secret)
STARTUP_READINESS = readiness_snapshot(REPOSITORY)
if not STARTUP_READINESS["ready"]:
    raise RuntimeError("RoyaltyRecover production readiness failed: " + ", ".join(STARTUP_READINESS["reasons"]))

app = create_app(api_keys=RAW_CREDENTIALS, repository=REPOSITORY)
app.config["MAX_CONTENT_LENGTH"] = CONFIG.max_body_bytes


@app.errorhandler(RequestEntityTooLarge)
def body_too_large(_error):
    return jsonify({"error": "payload_too_large", "max_bytes": CONFIG.max_body_bytes}), 413


@app.after_request
def production_headers(response):
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


def _admin_required():
    role = str(getattr(request, "royaltyrecover_role", ""))
    if not role_allows(role, "ADMIN"):
        return jsonify({"error": "insufficient_role", "required_role": "ADMIN"}), 403
    return None


@app.get("/api/v1/production/readiness")
def production_readiness():
    denied = _admin_required()
    if denied:
        return denied
    snapshot = readiness_snapshot(REPOSITORY)
    return jsonify({"ready": snapshot["ready"], "environment": snapshot["environment"]}), (200 if snapshot["ready"] else 503)


@app.post("/api/v1/agreements/<agreement_id>/retention")
def schedule_retention(agreement_id: str):
    denied = _admin_required()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    try:
        item = REPOSITORY.schedule_retention(
            str(request.royaltyrecover_org_id),
            agreement_id,
            str(payload.get("purge_after") or ""),
            str(payload.get("reason") or ""),
            str(request.royaltyrecover_actor_id),
        )
    except ValueError as exc:
        return jsonify({"error": "invalid_input", "detail": str(exc)}), 400
    return jsonify({"retention": item}), 200


@app.delete("/api/v1/agreements/<agreement_id>")
def purge_agreement(agreement_id: str):
    denied = _admin_required()
    if denied:
        return denied
    try:
        deleted = REPOSITORY.purge_agreement(
            str(request.royaltyrecover_org_id), agreement_id, str(request.royaltyrecover_actor_id)
        )
    except LookupError:
        return jsonify({"error": "not_found"}), 404
    except (ValueError, RuntimeError) as exc:
        return jsonify({"error": "purge_failed", "detail": str(exc)}), 409
    return jsonify({"ok": True, "deleted": deleted}), 200


@app.post("/api/v1/retention/purge-due")
def purge_due():
    denied = _admin_required()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    as_of = str(payload.get("as_of") or datetime.now(timezone.utc).isoformat())
    result = REPOSITORY.purge_due(
        str(request.royaltyrecover_org_id), as_of, str(request.royaltyrecover_actor_id)
    )
    return jsonify(result), 200
