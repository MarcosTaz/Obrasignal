from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Blueprint, jsonify, make_response, request
from werkzeug.exceptions import BadRequest

from vertical_apps.industrial_claims.change_capture import ChangeCaptureError, ChangeCaptureStore


IdentityResolver = Callable[[], tuple[str, str]]


def create_change_capture_blueprint(
    *,
    store: ChangeCaptureStore,
    capture_identity: IdentityResolver,
) -> Blueprint:
    blueprint = Blueprint("causledger_change_capture", __name__)

    def json_object() -> dict[str, Any]:
        payload = request.get_json(force=True)
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    @blueprint.get("/findings/<path:finding_id>/change-capture")
    def change_capture_status(finding_id: str):
        try:
            tenant_id, _actor_id = capture_identity()
            return jsonify(store.status(tenant_id=tenant_id, finding_id=finding_id))
        except ChangeCaptureError as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.post("/findings/<path:finding_id>/change-facts")
    def add_change_fact(finding_id: str):
        try:
            tenant_id, actor_id = capture_identity()
            payload = json_object()
            if payload.get("confirm_factual_entry") is not True:
                raise ValueError("confirm_factual_entry must be true")
            fact = store.add_fact(
                tenant_id=tenant_id,
                finding_id=finding_id,
                actor_id=actor_id,
                fact_type=str(payload["fact_type"]),
                fact_text=str(payload["fact_text"]),
                source_ref=None if payload.get("source_ref") is None else str(payload["source_ref"]),
            )
            return jsonify({
                "fact_receipt": {
                    "fact_id": fact["fact_id"],
                    "fact_type": fact["fact_type"],
                    "recorded_at": fact["recorded_at"],
                    "fact_hash": fact["fact_hash"],
                    "previous_fact_hash": fact["previous_fact_hash"],
                },
                "capture": store.status(tenant_id=tenant_id, finding_id=finding_id),
                "fact_entry_does_not_establish_recoverability": True,
            }), 201
        except (BadRequest, KeyError, ValueError, ChangeCaptureError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.get("/findings/<path:finding_id>/change-sheet")
    def download_change_sheet(finding_id: str):
        try:
            tenant_id, actor_id = capture_identity()
            status = store.status(tenant_id=tenant_id, finding_id=finding_id)
            sheet, digest = store.render_sheet(tenant_id=tenant_id, finding_id=finding_id)
            download = store.record_download(
                tenant_id=tenant_id,
                finding_id=finding_id,
                actor_id=actor_id,
                sheet_sha256=digest,
            )
            response = make_response(sheet)
            response.headers["Content-Type"] = "text/plain; charset=utf-8"
            response.headers["Content-Disposition"] = (
                f'attachment; filename="CausLedger-change-{status["sheet_id"]}.txt"'
            )
            response.headers["X-CausLedger-Sheet-SHA256"] = digest
            response.headers["X-CausLedger-Download-Receipt"] = download["download_id"]
            return response
        except ChangeCaptureError as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    return blueprint
