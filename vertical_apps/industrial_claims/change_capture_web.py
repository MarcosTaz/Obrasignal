from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Blueprint, jsonify, make_response, render_template, request
from werkzeug.exceptions import BadRequest

from vertical_apps.industrial_claims.change_capture import ChangeCaptureError, ChangeCaptureStore
from vertical_apps.industrial_claims.change_capture_reminder import ChangeCaptureReminderError, ChangeCaptureReminderService
from vertical_apps.industrial_claims.change_sheet_trust import ChangeSheetTrustError, ChangeSheetTrustService
from vertical_apps.industrial_claims.change_supplement import ChangeSupplementError, LateChangeSupplementStore
from vertical_apps.industrial_claims.proof import sha256_hex
from vertical_apps.industrial_claims.proof_providers import ProofProviderBundle


IdentityResolver = Callable[[], tuple[str, str]]


def _canonical_vindorum_sheet(sheet: str) -> tuple[str, str]:
    marker = "\nSnapshot SHA-256:"
    body, separator, _old_digest = sheet.rpartition(marker)
    if not separator:
        raise ChangeCaptureError("change sheet snapshot digest marker is missing")
    canonical_body = body.replace(
        "CAUSLEDGER — CHANGE CAPTURE SHEET",
        "VINDORUM — CHANGE CAPTURE SHEET",
    ).replace(
        "CausLedger first recorded at:",
        "VINDORUM first recorded at:",
    )
    digest = sha256_hex(canonical_body.encode("utf-8"))
    return f"{canonical_body}{marker} {digest}\n", digest


class _VindorumChangeCaptureView:
    """Expose canonical VINDORUM sheet bytes without rewriting legacy storage IDs."""

    def __init__(self, delegate: ChangeCaptureStore) -> None:
        self._delegate = delegate
        self.path = delegate.path

    def __getattr__(self, name: str):
        return getattr(self._delegate, name)

    def render_sheet(self, *, tenant_id: str, finding_id: str) -> tuple[str, str]:
        sheet, _legacy_digest = self._delegate.render_sheet(tenant_id=tenant_id, finding_id=finding_id)
        return _canonical_vindorum_sheet(sheet)


def create_change_capture_blueprint(
    *,
    store: ChangeCaptureStore,
    capture_identity: IdentityResolver,
    trust_service: ChangeSheetTrustService | None = None,
    supplement_store: LateChangeSupplementStore | None = None,
    reminder_service: ChangeCaptureReminderService | None = None,
) -> Blueprint:
    blueprint = Blueprint("causledger_change_capture", __name__)
    canonical_store = _VindorumChangeCaptureView(store)
    active_trust = trust_service or ChangeSheetTrustService(
        store.path,
        capture_store=canonical_store,
        qualified_timestamp_provider=ProofProviderBundle.fail_closed().qualified_timestamp,
    )
    active_trust.capture_store = canonical_store
    supplements = supplement_store or LateChangeSupplementStore(
        store.path,
        capture_store=store,
    )
    reminders = reminder_service or ChangeCaptureReminderService(
        store.path,
        capture_store=canonical_store,
    )
    reminders.capture_store = canonical_store

    def json_object() -> dict[str, Any]:
        payload = request.get_json(force=True)
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def capture_with_trust(*, tenant_id: str, finding_id: str) -> dict[str, Any]:
        capture = store.status(tenant_id=tenant_id, finding_id=finding_id)
        capture["snapshot_time_trust"] = active_trust.status(
            tenant_id=tenant_id,
            finding_id=finding_id,
        )
        reminder = reminders.status(tenant_id=tenant_id, finding_id=finding_id)
        capture["download_reminder"] = reminder
        capture["download_prompt"] = {
            **dict(capture.get("download_prompt") or {}),
            "active": reminder["should_prompt"],
            "message": reminder["message"],
            "current_snapshot_exported": reminder["current_snapshot_exported"],
            "current_sheet_sha256": reminder["current_sheet_sha256"],
            "next_milestone": reminder["next_milestone"],
            "stops_when_factual_window_closes": True,
        }
        supplement_status = supplements.status(tenant_id=tenant_id, finding_id=finding_id)
        capture["late_supplements"] = {
            "available": supplement_status["available"],
            "count": supplement_status["count"],
            "late_supplement_does_not_reopen_contemporaneous_window": True,
            "status_path": f"/findings/{finding_id}/late-supplements",
            "sheet_path": f"/findings/{finding_id}/late-supplement-sheet",
        }
        return capture

    @blueprint.get("/findings/<path:finding_id>/change-capture/view")
    def change_capture_view(finding_id: str):
        try:
            tenant_id, _actor_id = capture_identity()
            capture = capture_with_trust(tenant_id=tenant_id, finding_id=finding_id)
            return render_template("change_capture.html", capture=capture)
        except (ChangeCaptureError, ChangeCaptureReminderError, ChangeSheetTrustError, ChangeSupplementError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.get("/findings/<path:finding_id>/change-capture")
    def change_capture_status(finding_id: str):
        try:
            tenant_id, _actor_id = capture_identity()
            return jsonify(capture_with_trust(tenant_id=tenant_id, finding_id=finding_id))
        except (ChangeCaptureError, ChangeCaptureReminderError, ChangeSheetTrustError, ChangeSupplementError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.get("/findings/<path:finding_id>/change-sheet/trust")
    def change_sheet_trust(finding_id: str):
        try:
            tenant_id, _actor_id = capture_identity()
            return jsonify(active_trust.status(tenant_id=tenant_id, finding_id=finding_id))
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
        except (BadRequest, KeyError, ValueError, ChangeCaptureError, ChangeCaptureReminderError, ChangeSheetTrustError, ChangeSupplementError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.get("/findings/<path:finding_id>/change-sheet")
    def download_change_sheet(finding_id: str):
        try:
            tenant_id, actor_id = capture_identity()
            status = store.status(tenant_id=tenant_id, finding_id=finding_id)
            sheet, digest = canonical_store.render_sheet(tenant_id=tenant_id, finding_id=finding_id)
            payload = active_trust.detached_export_payload(sheet, digest)
            timestamp = active_trust.attest_snapshot(
                tenant_id=tenant_id,
                finding_id=finding_id,
                sheet_id=str(status["sheet_id"]),
                payload=payload,
                sheet_sha256=digest,
                factual_window_closes_at=str(status["factual_window_closes_at"]),
            )
            export = store.record_download(
                tenant_id=tenant_id,
                finding_id=finding_id,
                actor_id=actor_id,
                sheet_sha256=digest,
            )
            response = make_response(payload)
            response.headers["Content-Type"] = "text/plain; charset=utf-8"
            response.headers["Content-Disposition"] = (
                f'attachment; filename="vindorum-change-{status["sheet_id"]}.txt"'
            )
            response.headers["X-VINDORUM-Sheet-SHA256"] = digest
            response.headers["X-VINDORUM-Export-Receipt"] = export["download_id"]
            response.headers["X-VINDORUM-Transfer-Completion-Proven"] = "false"
            response.headers["X-VINDORUM-Timestamp-State"] = str(timestamp["state"])
            response.headers["X-VINDORUM-Timestamp-Provider"] = str(timestamp["provider"])
            response.headers["X-VINDORUM-Timestamp-Attestation"] = str(timestamp["attestation_id"])
            response.headers["X-VINDORUM-Reminder-Satisfied-For-Snapshot"] = "true"
            return response
        except (ChangeCaptureError, ChangeCaptureReminderError, ChangeSheetTrustError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.get("/findings/<path:finding_id>/late-supplements")
    def late_supplement_status(finding_id: str):
        try:
            tenant_id, _actor_id = capture_identity()
            return jsonify(supplements.status(tenant_id=tenant_id, finding_id=finding_id))
        except (ChangeCaptureError, ChangeSupplementError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.post("/findings/<path:finding_id>/late-supplements")
    def add_late_supplement(finding_id: str):
        try:
            tenant_id, actor_id = capture_identity()
            payload = json_object()
            if payload.get("confirm_late_supplement") is not True:
                raise ValueError("confirm_late_supplement must be true")
            supplement = supplements.add(
                tenant_id=tenant_id,
                finding_id=finding_id,
                actor_id=actor_id,
                fact_text=str(payload["fact_text"]),
                reason_for_late_entry=str(payload["reason_for_late_entry"]),
                source_ref=None if payload.get("source_ref") is None else str(payload["source_ref"]),
                declared_event_at=None if payload.get("declared_event_at") is None else str(payload["declared_event_at"]),
            )
            return jsonify({
                "supplement": supplement,
                "status": supplements.status(tenant_id=tenant_id, finding_id=finding_id),
                "contemporaneous_sheet_rewritten": False,
                "contemporaneous_window_reopened": False,
            }), 201
        except (BadRequest, KeyError, ValueError, ChangeCaptureError, ChangeSupplementError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.get("/findings/<path:finding_id>/late-supplement-sheet")
    def download_late_supplement_sheet(finding_id: str):
        try:
            tenant_id, _actor_id = capture_identity()
            status = supplements.status(tenant_id=tenant_id, finding_id=finding_id)
            if not status["available"]:
                raise ChangeSupplementError("late supplement sheet is only available after factual capture closes")
            sheet, digest = supplements.render_sheet(tenant_id=tenant_id, finding_id=finding_id)
            response = make_response(sheet)
            response.headers["Content-Type"] = "text/plain; charset=utf-8"
            response.headers["Content-Disposition"] = 'attachment; filename="vindorum-late-change-supplement.txt"'
            response.headers["X-VINDORUM-Late-Supplement-SHA256"] = digest
            response.headers["X-VINDORUM-Conventional-Change-Sheet-Rewritten"] = "false"
            return response
        except (ChangeCaptureError, ChangeSupplementError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    return blueprint
