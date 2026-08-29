from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from enum import Enum
from typing import Callable, Optional

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from .case_browser import render_case_browser
from .delivery_report import render_delivery_report
from .identifiers import CASE_ID_ADDRESSABILITY_ERROR, is_addressable_case_id
from .operator_ui import OPERATOR_HTML
from .repository import CapacityRepository
from .service import load_and_process, save_and_process
from .state import AssistedCaseState, exact_decimal_from_input, recovery_case_from_payload


TenantResolver = Callable[[object], Optional[str]]
MAX_REQUEST_BYTES = 1_000_000


_TOP_LEVEL_FIELDS = {
    "company_id",
    "customer_id",
    "program_id",
    "contract_id",
    "nomination_id",
    "forecast_units",
    "recovery_case",
    "evidence_refs",
    "missing_evidence",
    "deadline",
}


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    return value


def _required_string(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required and must be a string")
    return value


def _optional_string(payload: dict, key: str) -> Optional[str]:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string or null")
    return value


def _string_list(payload: dict, key: str) -> tuple[str, ...]:
    raw = payload.get(key, [])
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError(f"{key} must be a string list")
    return tuple(raw)


def _optional_decimal(payload: dict, key: str) -> Optional[Decimal]:
    raw = payload.get(key)
    if raw is None:
        return None
    return exact_decimal_from_input(raw, field_name=key)


def _addressable_recovery_case(raw: dict):
    recovery_case = recovery_case_from_payload(raw)
    if not is_addressable_case_id(recovery_case.case_id):
        raise ValueError(CASE_ID_ADDRESSABILITY_ERROR)
    return recovery_case


def _state_from_payload(payload: dict, tenant_id: str) -> AssistedCaseState:
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    unknown = set(payload) - _TOP_LEVEL_FIELDS
    if unknown:
        raise ValueError(f"unknown request fields: {sorted(unknown)}")

    for key in ("company_id", "customer_id", "program_id", "recovery_case"):
        if key not in payload:
            raise ValueError(f"{key} is required")

    return AssistedCaseState(
        tenant_id=tenant_id,
        company_id=_required_string(payload, "company_id"),
        customer_id=_required_string(payload, "customer_id"),
        program_id=_required_string(payload, "program_id"),
        recovery_case=_addressable_recovery_case(payload["recovery_case"]),
        evidence_refs=_string_list(payload, "evidence_refs"),
        missing_evidence=_string_list(payload, "missing_evidence"),
        deadline=_optional_string(payload, "deadline"),
        contract_id=_optional_string(payload, "contract_id"),
        nomination_id=_optional_string(payload, "nomination_id"),
        forecast_units=_optional_decimal(payload, "forecast_units"),
    )


def _processed_payload(processed) -> dict:
    state = processed.state
    return {
        "case": {
            "case_id": state.recovery_case.case_id,
            "company_id": state.company_id,
            "customer_id": state.customer_id,
            "program_id": state.program_id,
            "contract_id": state.contract_id,
            "nomination_id": state.nomination_id,
            "forecast_units": state.forecast_units,
            "commitment_state": state.recovery_case.commitment_state.value,
            "committed_units": state.recovery_case.committed_units,
            "actual_units": state.recovery_case.actual_units,
        },
        "result": asdict(processed.result),
        "recovery_package": asdict(processed.recovery_package),
        "delivery_report_markdown": render_delivery_report(
            state,
            processed.recovery_package,
        ),
    }


def create_app(repository: CapacityRepository, tenant_resolver: TenantResolver) -> Flask:
    """Create an isolated assisted-service Flask app.

    There is intentionally no insecure default tenant resolver and this app is
    not registered into the main ObraSignal runtime by this factory lane.
    """

    if repository is None:
        raise ValueError("repository is required")
    if not callable(tenant_resolver):
        raise ValueError("tenant_resolver is required")

    app = Flask("capacity_commitment_assisted")
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES

    @app.before_request
    def require_tenant():
        try:
            tenant_id = tenant_resolver(request)
        except Exception:
            return jsonify({"error": "authentication_failed"}), 401
        if not tenant_id or not str(tenant_id).strip():
            return jsonify({"error": "authentication_required"}), 401
        g.capacity_tenant_id = str(tenant_id)
        return None

    @app.after_request
    def security_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Capacity-Commitment"] = "assisted-t1"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    @app.errorhandler(ValueError)
    def invalid_input(exc):
        return jsonify({"error": "invalid_input", "detail": str(exc)}), 400

    @app.errorhandler(FileExistsError)
    def case_conflict(_exc):
        return jsonify({"error": "case_already_exists"}), 409

    @app.errorhandler(KeyError)
    def not_found(_exc):
        return jsonify({"error": "case_not_found"}), 404

    @app.errorhandler(RuntimeError)
    def reassessment_required(exc):
        if "engine version drift" in str(exc):
            return jsonify({"error": "reassessment_required"}), 409
        return jsonify({"error": "runtime_integrity_failure"}), 500

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_exc):
        return jsonify({"error": "request_too_large"}), 413

    @app.route("/", methods=["GET"])
    def operator_console():
        console = OPERATOR_HTML.replace(
            '<form id="case-form">',
            '<p><a href="/cases">Open existing tenant cases</a></p><form id="case-form">',
            1,
        )
        return console, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.route("/cases", methods=["GET"])
    def case_browser():
        case_ids = repository.list_case_ids(tenant_id=g.capacity_tenant_id)
        return render_case_browser(case_ids), 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.route("/api/capacity/cases", methods=["GET"])
    def list_cases():
        items = repository.list_case_ids(tenant_id=g.capacity_tenant_id)
        return jsonify({"items": items, "count": len(items)})

    @app.route("/api/capacity/cases", methods=["POST"])
    def create_case():
        if request.headers.get("X-Capacity-Intent") != "create-case":
            return jsonify({"error": "create_intent_required"}), 403
        payload = request.get_json(silent=False)
        state = _state_from_payload(payload, g.capacity_tenant_id)
        processed = save_and_process(repository, state)
        return jsonify(_json_safe(_processed_payload(processed))), 201

    @app.route("/api/capacity/cases/<case_id>", methods=["GET"])
    def get_case(case_id: str):
        processed = load_and_process(
            repository,
            tenant_id=g.capacity_tenant_id,
            case_id=case_id,
        )
        return jsonify(_json_safe(_processed_payload(processed)))

    @app.route("/api/capacity/cases/<case_id>/report", methods=["GET"])
    def get_case_report(case_id: str):
        processed = load_and_process(
            repository,
            tenant_id=g.capacity_tenant_id,
            case_id=case_id,
        )
        report = render_delivery_report(
            processed.state,
            processed.recovery_package,
        )
        return report, 200, {"Content-Type": "text/markdown; charset=utf-8"}

    return app