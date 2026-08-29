from __future__ import annotations

import json
import os
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Flask, jsonify, request

from authz import CredentialRegistry, role_allows
from contract_store import ContractStore
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


def _load_api_key_config():
    raw = os.getenv("ROYALTYRECOVER_API_KEYS_JSON", "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


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


def create_app(api_keys=None, repository: RoyaltyRepository | None = None) -> Flask:
    app = Flask(__name__)
    registry = CredentialRegistry.from_config(api_keys if api_keys is not None else _load_api_key_config())
    repo = repository or RoyaltyRepository.file(os.getenv("ROYALTYRECOVER_DB_PATH", "royaltyrecover.db"))
    contracts = ContractStore(repo)

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
        if not registry.configured:
            return jsonify({"error": "service_not_configured"}), 503
        credential = registry.authenticate(request.headers.get("X-RoyaltyRecover-API-Key", ""))
        if credential is None:
            return jsonify({"error": "authentication_required"}), 401
        request.royaltyrecover_org_id = credential.organization_id
        request.royaltyrecover_actor_id = f"api:{credential.key_id}"
        request.royaltyrecover_role = credential.role
        return None

    def org_id() -> str:
        return request.royaltyrecover_org_id

    def actor_id() -> str:
        return request.royaltyrecover_actor_id

    def require_role(required_role: str):
        if not role_allows(request.royaltyrecover_role, required_role):
            return jsonify({"error": "insufficient_role", "required_role": required_role}), 403
        return None

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

    @app.post("/api/v1/agreement-versions/<version_id>/clauses")
    def create_clause(version_id):
        try:
            payload = _json_payload()
            item = contracts.add_clause(
                org_id(), version_id, str(payload.get("clause_ref") or ""), str(payload.get("clause_type") or ""), actor_id(),
                text_excerpt=payload.get("text_excerpt"), evidence_id=payload.get("evidence_id"), review_status="UNREVIEWED",
            )
        except ValueError as exc:
            return jsonify({"error": "invalid_input", "detail": str(exc)}), 400
        return jsonify({"clause": item}), 201

    @app.post("/api/v1/clauses/<clause_id>/review")
    def review_clause(clause_id):
        denied = require_role("REVIEWER")
        if denied:
            return denied
        try:
            payload = _json_payload()
            item = contracts.set_clause_review_status(
                org_id(), clause_id, str(payload.get("review_status") or ""), actor_id(), str(payload.get("rationale") or "")
            )
        except ValueError as exc:
            return jsonify({"error": "invalid_input", "detail": str(exc)}), 400
        return jsonify({"clause": item}), 200

    @app.post("/api/v1/agreement-versions/<version_id>/royalty-rules")
    def create_royalty_rule(version_id):
        try:
            payload = _json_payload()
            item = contracts.add_royalty_rule(
                org_id(), version_id, str(payload.get("clause_id") or ""), str(payload.get("basis") or ""),
                str(payload.get("currency") or ""), actor_id(),
                rate=_decimal(payload.get("rate")), per_unit=_decimal(payload.get("per_unit")),
                minimum_guarantee=_decimal(payload.get("minimum_guarantee")), cap=_decimal(payload.get("cap")),
                floor=_decimal(payload.get("floor")), effective_from=payload.get("effective_from"),
                effective_to=payload.get("effective_to"), review_status="UNREVIEWED",
            )
        except ValueError as exc:
            return jsonify({"error": "invalid_input", "detail": str(exc)}), 400
        return jsonify({"royalty_rule": item}), 201

    @app.post("/api/v1/royalty-rules/<rule_id>/review")
    def review_royalty_rule(rule_id):
        denied = require_role("REVIEWER")
        if denied:
            return denied
        try:
            payload = _json_payload()
            item = contracts.set_rule_review_status(
                org_id(), rule_id, str(payload.get("review_status") or ""), actor_id(), str(payload.get("rationale") or "")
            )
        except ValueError as exc:
            return jsonify({"error": "invalid_input", "detail": str(exc)}), 400
        return jsonify({"royalty_rule": item}), 200

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
