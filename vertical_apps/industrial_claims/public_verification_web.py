from __future__ import annotations

import secrets
from collections.abc import Callable
from typing import Any

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import BadRequest

from vertical_apps.industrial_claims.durable_proof import build_durable_claim_proof_pack
from vertical_apps.industrial_claims.public_verification import build_public_receipt, new_verification_id
from vertical_apps.industrial_claims.public_verification_store import (
    PublicVerificationStore,
    PublicVerificationStoreError,
)
from vertical_apps.industrial_claims.service import IndustrialClaimsService


IdentityResolver = Callable[[], tuple[str, str]]


def create_public_verification_blueprint(
    *,
    service: IndustrialClaimsService,
    store: PublicVerificationStore,
    publication_identity: IdentityResolver,
) -> Blueprint:
    """Build the public proof surface without exposing private case routes.

    ``publication_identity`` must enforce the application's authenticated role
    policy and return the verified tenant/actor. Public lookup itself deliberately
    requires only possession of a high-entropy verification token.
    """
    blueprint = Blueprint("causledger_public_verification", __name__)

    def json_object() -> dict[str, Any]:
        payload = request.get_json(force=True)
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    @blueprint.get("/verify/<verification_id>")
    def verify_public(verification_id: str):
        try:
            return jsonify(store.get_public(verification_id))
        except PublicVerificationStoreError:
            # Public callers receive a deliberately non-enumerable generic miss.
            return jsonify({"error": "verification_not_found"}), 404

    @blueprint.post("/findings/<path:finding_id>/public-verification")
    def publish_public(finding_id: str):
        try:
            tenant_id, actor_id = publication_identity()
            payload = json_object()
            if payload.get("confirm_publication") is not True:
                raise ValueError("confirm_publication must be true")
            pack = build_durable_claim_proof_pack(
                service,
                tenant_id=tenant_id,
                finding_id=finding_id,
            )
            token = new_verification_id()
            receipt = build_public_receipt(pack, verification_id=token)
            store.publish(
                tenant_id=tenant_id,
                subject_ref=finding_id,
                receipt=receipt,
                actor_id=actor_id,
            )
            return jsonify({
                "verification_id": token,
                "verification_path": f"/verify/{token}",
                "receipt": receipt,
                "private_case_fields_published": False,
                "external_claim_submission_performed": False,
            }), 201
        except (BadRequest, ValueError, PublicVerificationStoreError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.post("/verify/<verification_id>/withdraw")
    def withdraw_public(verification_id: str):
        try:
            tenant_id, actor_id = publication_identity()
            payload = json_object()
            if payload.get("confirm_withdrawal") is not True:
                raise ValueError("confirm_withdrawal must be true")
            store.transition(
                tenant_id=tenant_id,
                verification_id=verification_id,
                event_id=f"withdraw-{secrets.token_urlsafe(18)}",
                event_type="WITHDRAWN",
                reason=str(payload["reason"]),
                actor_id=actor_id,
            )
            return jsonify({"verification_id": verification_id, "state": "WITHDRAWN"})
        except (BadRequest, KeyError, ValueError, PublicVerificationStoreError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.post("/verify/<verification_id>/supersede")
    def supersede_public(verification_id: str):
        try:
            tenant_id, actor_id = publication_identity()
            payload = json_object()
            if payload.get("confirm_supersession") is not True:
                raise ValueError("confirm_supersession must be true")
            successor = str(payload["successor_verification_id"])
            store.transition(
                tenant_id=tenant_id,
                verification_id=verification_id,
                event_id=f"supersede-{secrets.token_urlsafe(18)}",
                event_type="SUPERSEDED",
                successor_verification_id=successor,
                reason=str(payload["reason"]),
                actor_id=actor_id,
            )
            return jsonify({
                "verification_id": verification_id,
                "state": "SUPERSEDED",
                "successor_verification_id": successor,
            })
        except (BadRequest, KeyError, ValueError, PublicVerificationStoreError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    return blueprint
