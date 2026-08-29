from __future__ import annotations

import hmac
import json
import os
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Flask, jsonify, request

from repository import ConflictError, NotFoundError, RoyaltyRepository, ScopeError
from royalty_engine import PeriodInput, RoyaltyRule, RoyaltyTier
from service_pipeline import RecoverabilityCase, pack_to_dict, run_case


MAX_TEXT_EVIDENCE_BYTES = 1_000_000


def _decimal(value, *, required=False):
    if value is None or value == "":
        if required:
            raise ValueError("required decimal is missing")
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid decimal: {value}") from exc
    if not parsed.is_finite():
        raise ValueError("decimal must be finite")
    return parsed


def _date(value):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"invalid ISO date: {value}") from exc


def _bool_or_none(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise ValueError("expected boolean or null")


def _load_api_keys() -> dict[str, str]:
    raw = os.getenv("ROYALTYRECOVER_API_KEYS_JSON", "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(org_id).strip(): str(secret)
        for org_id, secret in payload.items()
        if str(org_id).strip() and isinstance(secret, str) and secret
    }


def _text_content(payload: dict, field: str = "content_utf8") -> bytes:
    content = payload.get(field)
    if not isinstance(content, str) or not content:
        raise ValueError(f"{field} is required and must be non-empty UTF-8 text")
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_TEXT_EVIDENCE_BYTES:
        raise ValueError(f"{field} exceeds {MAX_TEXT_EVIDENCE_BYTES} byte limit")
    return encoded


def _json_payload() -> dict:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    return payload


def _rule(payload):
    tiers = tuple(
        RoyaltyTier(
            lower_bound=_decimal(item.get("lower_bound"), required=True),
            upper_bound=_decimal(item.get("upper_bound")),
            rate=_decimal(item.get("rate"), required=True),
            source_clause=item.get("source_clause"),
        )
        for item in payload.get("tiers", [])
    )
    return RoyaltyRule(
        rule_id=str(payload.get("rule_id") or ""),
        basis=str(payload.get("basis") or ""),
        rate=_decimal(payload.get("rate")),
        per_unit=_decimal(payload.get("per_unit")),
        minimum_guarantee=_decimal(payload.get("minimum_guarantee")),
        cap=_decimal(payload.get("cap")),
        floor=_decimal(payload.get("floor")),
        tiers=tiers,
        sublicense_share=_decimal(payload.get("sublicense_share")),
        currency=str(payload.get("currency") or "EUR").upper(),
        source_clause=payload.get("source_clause"),
        requires_professional_review=bool(payload.get("requires_professional_review", False)),
    )


def _period(payload):
    return PeriodInput(
        gross_sales=_decimal(payload.get("gross_sales")),
        units=_decimal(payload.get("units")),
        permitted_deductions=_decimal(payload.get("permitted_deductions")),
        sublicense_revenue=_decimal(payload.get("sublicense_revenue")),
        reported_royalty=_decimal(payload.get("reported_royalty")),
        paid_royalty=_decimal(payload.get("paid_royalty")),
        source_currency=(str(payload.get("source_currency")).upper() if payload.get("source_currency") else None),
        fx_rate_to_rule_currency=_decimal(payload.get("fx_rate_to_rule_currency")),
        fx_rate_date=_date(payload.get("fx_rate_date")),
        fx_evidence_id=payload.get("fx_evidence_id"),
        source_data_complete=bool(payload.get("source_data_complete", True)),
        duplicate_transactions_detected=bool(payload.get("duplicate_transactions_detected", False)),
        conflicting_datasets=bool(payload.get("conflicting_datasets", False)),
    )


def create_app(api_keys: dict[str, str] | None = None, repository: RoyaltyRepository | None = None) -> Flask:
    app = Flask(__name__)
    configured_keys = dict(api_keys) if api_keys is not None else _load_api_keys()
    repo = repository or RoyaltyRepository.file(os.getenv("ROYALTYRECOVER_DB_PATH", "royaltyrecover.db"))

    @app.after_request
    def security_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.errorhandler(NotFoundError)
    def not_found(error):
        return jsonify({"error": "not_found", "detail": str(error)}), 404

    @app.errorhandler(ConflictError)
    def conflict(error):
        return jsonify({"error": "conflict", "detail": str(error)}), 409

    @app.errorhandler(ScopeError)
    def scope_error(error):
        return jsonify({"error": "scope_conflict", "detail": str(error)}), 409

    @app.get("/health")
    def health():
        return jsonify({"ok": True, "service": "RoyaltyRecover", "claim_generation": False})

    @app.before_request
    def authenticate():
        if request.path == "/health":
            return None
        if not configured_keys:
            return jsonify({"error": "service_not_configured"}), 503
        supplied = request.headers.get("X-RoyaltyRecover-API-Key", "")
        authenticated_org = None
        for org_id, expected in configured_keys.items():
            if hmac.compare_digest(supplied, expected):
                authenticated_org = org_id
                break
        if authenticated_org is None:
            return jsonify({"error": "authentication_required"}), 401
        request.royaltyrecover_org_id = authenticated_org
        request.royaltyrecover_actor_id = f"api:{authenticated_org}"
        return None

    def org_id() -> str:
        return request.royaltyrecover_org_id

    def actor_id() -> str:
        return request.royaltyrecover_actor_id

    @app.post("/api/v1/organization")
    def organization():
        try:
            payload = _json_payload()
            item = repo.ensure_organization(org_id(), str(payload.get("name") or ""), actor_id())
        except ValueError as exc:
            return jsonify({"error": "invalid_input", "detail": str(exc)}), 400
        return jsonify({"organization": item}), 200

    @app.post("/api/v1/licensors")
    def create_licensor():
        try:
            payload = _json_payload()
            item = repo.create_licensor(org_id(), str(payload.get("legal_name") or ""), actor_id())
        except ValueError as exc:
            return jsonify({"error": "invalid_input", "detail": str(exc)}), 400
        return jsonify({"licensor": item}), 201

    @app.post("/api/v1/licensees")
    def create_licensee():
        try:
            payload = _json_payload()
            item = repo.create_licensee(org_id(), str(payload.get("legal_name") or ""), actor_id())
        except ValueError as exc:
            return jsonify({"error": "invalid_input", "detail": str(exc)}), 400
        return jsonify({"licensee": item}), 201

    @app.post("/api/v1/agreements")
    def create_agreement():
        try:
            payload = _json_payload()
            item = repo.create_agreement(
                org_id(),
                str(payload.get("licensor_id") or ""),
                str(payload.get("licensee_id") or ""),
                str(payload.get("title") or ""),
                actor_id(),
                governing_law=payload.get("governing_law"),
            )
        except ValueError as exc:
            return jsonify({"error": "invalid_input", "detail": str(exc)}), 400
        return jsonify({"agreement": item}), 201

    @app.get("/api/v1/agreements/<agreement_id>")
    def get_agreement(agreement_id):
        return jsonify({"agreement": repo.get_agreement(org_id(), agreement_id)})

    @app.post("/api/v1/agreements/<agreement_id>/versions")
    def create_agreement_version(agreement_id):
        try:
            payload = _json_payload()
            content = _text_content(payload)
            item = repo.add_agreement_version(
                org_id(), agreement_id, str(payload.get("version_label") or ""), content, actor_id(),
                effective_from=payload.get("effective_from"),
                effective_to=payload.get("effective_to"),
                source_uri=payload.get("source_uri"),
            )
        except ValueError as exc:
            return jsonify({"error": "invalid_input", "detail": str(exc)}), 400
        response = dict(item)
        response["content_persisted"] = False
        response["lineage_note"] = "Raw text is hashed for lineage and discarded by this minimum endpoint."
        return jsonify({"agreement_version": response}), 201

    @app.post("/api/v1/evidence")
    def create_evidence():
        try:
            payload = _json_payload()
            content = _text_content(payload)
            item = repo.add_evidence(
                org_id(), str(payload.get("evidence_type") or ""), content, actor_id(),
                source_uri=payload.get("source_uri"), metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
            )
        except ValueError as exc:
            return jsonify({"error": "invalid_input", "detail": str(exc)}), 400
        response = dict(item)
        response["content_persisted"] = False
        response["lineage_note"] = "Raw text is hashed for lineage and discarded by this minimum endpoint."
        return jsonify({"evidence": response}), 201

    @app.get("/api/v1/audit-events")
    def audit_events():
        return jsonify({"items": repo.list_audit_events(org_id())})

    @app.post("/api/v1/recoverability/scan")
    def recoverability_scan():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_json"}), 400
        try:
            organization_id = str(payload.get("organization_id") or "").strip()
            case_id = str(payload.get("case_id") or "").strip()
            licensee_id = str(payload.get("licensee_id") or "").strip()
            agreement_id = str(payload.get("agreement_id") or "").strip()
            if not all((organization_id, case_id, licensee_id, agreement_id)):
                raise ValueError("organization_id, case_id, licensee_id and agreement_id are required")
            if organization_id != org_id():
                return jsonify({"error": "organization_scope_mismatch"}), 403
            case = RecoverabilityCase(
                case_id=case_id,
                licensee_id=licensee_id,
                agreement_id=agreement_id,
                annual_reported_royalty=_decimal(payload.get("annual_reported_royalty")),
                audit_deadline=_date(payload.get("audit_deadline")),
                audit_right_supported=_bool_or_none(payload.get("audit_right_supported")),
                contract_version_complete=bool(payload.get("contract_version_complete", False)),
                auditor_requirement=payload.get("auditor_requirement"),
                rule=_rule(payload.get("rule") or {}),
                period_input=_period(payload.get("period_input") or {}),
            )
            today = _date(payload.get("as_of_date")) or date.today()
        except (TypeError, ValueError) as exc:
            return jsonify({"error": "invalid_input", "detail": str(exc)}), 400

        result = pack_to_dict(run_case(case, today=today))
        result["organization_id"] = organization_id
        result["disclaimer"] = "Analytical output only. Positive variance is not a legal claim or formal audit conclusion."
        return jsonify(result)

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.getenv("PORT", "8080")), debug=False)
