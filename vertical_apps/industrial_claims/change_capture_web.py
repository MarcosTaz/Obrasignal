from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Blueprint, jsonify, make_response, render_template, request
from werkzeug.exceptions import BadRequest

from vertical_apps.industrial_claims.change_capture import ChangeCaptureError, ChangeCaptureStore
from vertical_apps.industrial_claims.change_sheet_trust import ChangeSheetTrustError, ChangeSheetTrustService


IdentityResolver = Callable[[], tuple[str, str]]


def create_change_capture_blueprint(
    *,
    store: ChangeCaptureStore,
    capture_identity: IdentityResolver,
    trust_service: ChangeSheetTrustService | None = None,
) -> Blueprint:
    blueprint = Blueprint("causledger_change_capture", __name__)

    def json_object() -> dict[str, Any]:
        payload = request.get_json(force=True)
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def capture_with_trust(*, tenant_id: str, finding_id: str) -> dict[str, Any]:
        capture = store.status(tenant_id=tenant_id, finding_id=finding_id)
        if trust_service is not None:
            capture["snapshot_time_trust"] = trust_service.status(
                tenant_id=tenant_id,
                finding_id=finding_id,
            )
        else:
            capture["snapshot_time_trust"] = {
                "current_snapshot_externally_timestamped": False,
                "qualified_timestamp_claim_is_fail_closed": True,
                "provider_wiring_state": "NOT_CONFIGURED",
            }
        return capture

    @blueprint.get("/findings/<path:finding_id>/change-capture/view")
    def change_capture_view(finding_id: str):
        try:
            tenant_id, _actor_id = capture_identity()
            capture = capture_with_trust(tenant_id=tenant_id, finding_id=finding_id)
            return render_template("change_capture.html", capture=capture)
        except (ChangeCaptureError, ChangeSheetTrustError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.get("/findings/<path:finding_id>/change-capture")
    def change_capture_status(finding_id: str):
        try:
            tenant_id, _actor_id = capture_identity()
            return jsonify(capture_with_trust(tenant_id=tenant_id, finding_id=finding_id))
        except (ChangeCaptureError, ChangeSheetTrustError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.get("/findings/<path:finding_id>/change-sheet/trust")
    def change_sheet_trust(finding_id: str):
        try:
            tenant_id, _actor_id = capture_identity()
            if trust_service is None:
                return jsonify({
                    "current_snapshot_externally_timestamped": False,
                    "qualified_timestamp_claim_is_fail_closed": True,
                    "provider_wiring_state": "NOT_CONFIGURED",
                })
            return jsonify(trust_service.status(tenant_id=tenant_id, finding_id=finding_id))
        except (ChangeCaptureError, ChangeSheetTrustError) as exc:
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
                "capture": capture_with_trust(tenant_id=tenant_id, finding_id=finding_id),
                "fact_entry_does_not_establish_recoverability": True,
            }), 201
        except (BadRequest, KeyError, ValueError, ChangeCaptureError, ChangeSheetTrustError) as exc:
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
            timestamp = None
            if trust_service is not None:
                timestamp = trust_service.attest_current(tenant_id=tenant_id, finding_id=finding_id)
            response = make_response(sheet)
            response.headers["Content-Type"] = "text/plain; charset=utf-8"
            response.headers["Content-Disposition"] = (
                f'attachment; filename="CausLedger-change-{status["sheet_id"]}.txt"'
            )
            response.headers["X-CausLedger-Sheet-SHA256"] = digest
            response.headers["X-CausLedger-Download-Receipt"] = download["download_id"]
            if timestamp is not None:
                response.headers["X-CausLedger-Timestamp-State"] = str(timestamp["state"])
                response.headers["X-CausLedger-Timestamp-Provider"] = str(timestamp["provider"])
                response.headers["X-CausLedger-Timestamp-Attestation"] = str(timestamp["attestation_id"])
            return response
        except (ChangeCaptureError, ChangeSheetTrustError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    return blueprint