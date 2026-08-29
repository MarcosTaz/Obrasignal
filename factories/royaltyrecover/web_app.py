from __future__ import annotations

import hmac
import os
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Flask, jsonify, request

from royalty_engine import PeriodInput, RoyaltyRule, RoyaltyTier
from service_pipeline import RecoverabilityCase, pack_to_dict, run_case


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


def create_app(api_key: str | None = None) -> Flask:
    app = Flask(__name__)
    configured_key = api_key if api_key is not None else os.getenv("ROYALTYRECOVER_API_KEY")

    @app.after_request
    def security_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/health")
    def health():
        return jsonify({"ok": True, "service": "RoyaltyRecover", "claim_generation": False})

    @app.before_request
    def authenticate():
        if request.path == "/health":
            return None
        if not configured_key:
            return jsonify({"error": "service_not_configured"}), 503
        supplied = request.headers.get("X-RoyaltyRecover-API-Key", "")
        if not hmac.compare_digest(supplied, configured_key):
            return jsonify({"error": "authentication_required"}), 401
        return None

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
