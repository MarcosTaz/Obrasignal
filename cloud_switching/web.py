from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Callable

from flask import Blueprint, jsonify, request
from jwt import InvalidTokenError

from auth_context_jwt import JwksUnavailableError

from .baseline import BaselineCost, Certainty, CurrentStateBaseline
from .domain import MigrationCase
from .estate import EstateAsset, EstateCertainty, InfrastructureEstate
from .forecast import FrozenMigrationForecast
from .incentives import Incentive, IncentiveStatus
from .options import OptionType, SwitchingOption, compare_options
from .service import build_decision_package
from .web_outcome import reconcile_payload


TenantResolver = Callable[[], str | None]


def _money(value, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a decimal value") from exc


def _optional_money(value, field: str):
    return None if value is None else _money(value, field)


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _baseline(tenant_id: str, body: dict) -> CurrentStateBaseline:
    components = []
    for item in body.get("baseline", []):
        certainty = Certainty(item.get("certainty", "unknown"))
        components.append(
            BaselineCost(
                name=str(item.get("name", "")),
                annual_value=_optional_money(item.get("annual_value"), "baseline.annual_value"),
                certainty=certainty,
                material=bool(item.get("material", True)),
                source_id=item.get("source_id"),
            )
        )
    return CurrentStateBaseline(company_id=tenant_id, components=components)


def _migration_case(body: dict) -> MigrationCase:
    item = body["migration_case"]
    money_fields = (
        "current_annual_cost",
        "status_quo_annual_cost",
        "target_annual_cost",
        "migration_engineering_cost",
        "partner_services_cost",
        "internal_labour_cost",
        "training_cost",
        "parallel_run_cost",
        "refactoring_cost",
        "risk_contingency_cost",
        "data_movement_cost",
        "decommissioning_cost",
        "backup_dr_transition_cost",
        "security_transition_cost",
        "support_transition_cost",
        "provider_credit_approved",
        "provider_credit_received",
        "partner_incentive_approved",
        "partner_incentive_received",
    )
    values = {field: _money(item.get(field, "0"), f"migration_case.{field}") for field in money_fields}
    return MigrationCase(
        case_id=str(item.get("case_id", "")),
        observation_months=int(item.get("observation_months", 12)),
        actual_post_annual_cost=_optional_money(item.get("actual_post_annual_cost"), "migration_case.actual_post_annual_cost"),
        **values,
    )


def _incentives(body: dict) -> list[Incentive]:
    results = []
    for item in body.get("incentives", []):
        results.append(
            Incentive(
                incentive_id=str(item.get("incentive_id", "")),
                program=str(item.get("program", "")),
                status=IncentiveStatus(item.get("status", "unknown")),
                potential_amount=_optional_money(item.get("potential_amount"), "incentive.potential_amount"),
                approved_amount=_optional_money(item.get("approved_amount"), "incentive.approved_amount"),
                received_amount=_optional_money(item.get("received_amount"), "incentive.received_amount"),
                cap_amount=_optional_money(item.get("cap_amount"), "incentive.cap_amount"),
                eligibility_evidence_id=item.get("eligibility_evidence_id"),
                approval_evidence_id=item.get("approval_evidence_id"),
                receipt_evidence_id=item.get("receipt_evidence_id"),
            )
        )
    return results


def _options(body: dict) -> list[SwitchingOption]:
    results = []
    for item in body.get("options", []):
        results.append(
            SwitchingOption(
                option_id=str(item.get("option_id", "")),
                option_type=OptionType(item.get("option_type", "switch")),
                destination=str(item.get("destination", "")),
                currency=str(item.get("currency", "EUR")),
                annual_run_cost=_money(item.get("annual_run_cost", "0"), "option.annual_run_cost"),
                one_time_switching_cost=_money(item.get("one_time_switching_cost", "0"), "option.one_time_switching_cost"),
                received_incentives=_money(item.get("received_incentives", "0"), "option.received_incentives"),
            )
        )
    return results


def _forecast(body: dict, case: MigrationCase) -> FrozenMigrationForecast:
    item = body.get("forecast")
    if not isinstance(item, dict):
        raise ValueError("forecast object is required and must be frozen before analysis")
    forecast = FrozenMigrationForecast(
        case_id=str(item.get("case_id", "")).strip(),
        source_platform=str(item.get("source_platform", "")).strip(),
        destination_platform=str(item.get("destination_platform", "")).strip(),
        workload_class=str(item.get("workload_class", "")).strip(),
        migration_strategy=str(item.get("migration_strategy", "")).strip(),
        migration_cost=_money(item.get("migration_cost"), "forecast.migration_cost"),
        duration_days=_money(item.get("duration_days"), "forecast.duration_days"),
        annual_run_cost=_money(item.get("annual_run_cost"), "forecast.annual_run_cost"),
        downtime_minutes=_money(item.get("downtime_minutes"), "forecast.downtime_minutes"),
        incentive_total=_money(item.get("incentive_total"), "forecast.incentive_total"),
        methodology_version=str(item.get("methodology_version", "")).strip(),
    )
    forecast.validate_against_case(case)
    return forecast


def _estate(tenant_id: str, body: dict):
    item = body.get("estate")
    if not isinstance(item, dict):
        raise ValueError("estate object is required")
    as_of_raw = item.get("as_of")
    if not isinstance(as_of_raw, str) or not as_of_raw.strip():
        raise ValueError("estate.as_of is required")
    try:
        as_of = datetime.fromisoformat(as_of_raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("estate.as_of must be ISO-8601") from exc
    assets = []
    for asset in item.get("assets", []):
        last_seen_raw = asset.get("last_seen_at")
        last_seen = None
        if last_seen_raw is not None:
            if not isinstance(last_seen_raw, str):
                raise ValueError("estate asset last_seen_at must be ISO-8601")
            try:
                last_seen = datetime.fromisoformat(last_seen_raw.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("estate asset last_seen_at must be ISO-8601") from exc
        assets.append(
            EstateAsset(
                asset_id=str(asset.get("asset_id", "")),
                asset_type=str(asset.get("asset_type", "")),
                cpu_cores=asset.get("cpu_cores"),
                memory_gib=asset.get("memory_gib"),
                storage_gib=asset.get("storage_gib"),
                last_seen_at=last_seen,
                certainty=EstateCertainty(asset.get("certainty", "unknown")),
                source_id=asset.get("source_id"),
            )
        )
    assessment = InfrastructureEstate(company_id=tenant_id, assets=assets).assess(
        as_of=as_of,
        stale_after_days=int(item.get("stale_after_days", 30)),
    )
    if not assessment.decision_ready:
        raise ValueError("estate is not decision-ready")
    return assessment


def _assert_frozen_forecast(record, frozen: dict) -> None:
    identity_pairs = (
        (record.case_id, str(frozen.get("case_id", "")), "case_id"),
        (record.source_platform, str(frozen.get("source_platform", "")), "source_platform"),
        (record.destination_platform, str(frozen.get("destination_platform", "")), "destination_platform"),
        (record.workload_class, str(frozen.get("workload_class", "")), "workload_class"),
        (record.migration_strategy, str(frozen.get("migration_strategy", "")), "migration_strategy"),
    )
    for actual, expected, field in identity_pairs:
        if actual != expected:
            raise ValueError(f"outcome {field} does not match frozen forecast")

    numeric_pairs = (
        (record.migration_cost.forecast, "migration_cost"),
        (record.duration_days.forecast, "duration_days"),
        (record.annual_run_cost.forecast, "annual_run_cost"),
        (record.downtime_minutes.forecast, "downtime_minutes"),
        (record.provider_incentive.forecast, "incentive_total"),
    )
    for supplied, field in numeric_pairs:
        if supplied != Decimal(str(frozen.get(field))):
            raise ValueError(f"outcome forecast {field} does not match frozen forecast")


def create_blueprint(*, workspace, resolve_tenant: TenantResolver) -> Blueprint:
    blueprint = Blueprint("cloud_switching", __name__, url_prefix="/cloud-switching")

    def tenant_or_error():
        try:
            tenant_id = resolve_tenant()
        except JwksUnavailableError:
            return None, (jsonify({"error": "authentication_service_unavailable"}), 503)
        except (RuntimeError, InvalidTokenError):
            return None, (jsonify({"error": "authentication_required"}), 401)
        if not tenant_id or not tenant_id.strip():
            return None, (jsonify({"error": "authentication_required"}), 401)
        return tenant_id, None

    @blueprint.get("/health")
    def health():
        return jsonify({"service": "cloud-switching", "status": "ok"})

    @blueprint.post("/api/analyze")
    def analyze():
        tenant_id, error = tenant_or_error()
        if error:
            return error
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "JSON object required"}), 400
        package_id = str(body.get("package_id", "")).strip()
        if not package_id:
            return jsonify({"error": "package_id required"}), 400
        try:
            estate_assessment = _estate(tenant_id, body)
            baseline = _baseline(tenant_id, body)
            case = _migration_case(body)
            incentives = _incentives(body)
            options = _options(body)
            if len(options) < 2:
                raise ValueError("at least two switching options are required")
            option_comparison = compare_options(
                options,
                horizon_years=int(body.get("horizon_years", 3)),
            )
            forecast = _forecast(body, case)
            destinations = {option.destination for option in options}
            if forecast.destination_platform not in destinations:
                raise ValueError("forecast destination must match a compared option")
            package = build_decision_package(baseline, case, incentives)
            stored = workspace.save(
                tenant_id=tenant_id,
                package_id=package_id,
                package=package,
            )
            delivery_payload = {
                "estate": _json_safe(asdict(estate_assessment)),
                "decision": _json_safe(asdict(package)),
                "options": _json_safe(asdict(option_comparison)),
                "forecast": _json_safe(asdict(forecast)),
                "outcome": None,
            }
            stored_delivery = None
            if hasattr(workspace, "save_delivery"):
                stored_delivery = workspace.save_delivery(
                    tenant_id=tenant_id,
                    package_id=package_id,
                    payload=delivery_payload,
                )
        except (KeyError, TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 422
        response = {
            "package_id": package_id,
            "version": stored.version,
            "content_hash": stored.content_hash,
            "estate_assessment": delivery_payload["estate"],
            "decision_package": delivery_payload["decision"],
            "option_comparison": delivery_payload["options"],
            "frozen_forecast": delivery_payload["forecast"],
        }
        if stored_delivery is not None:
            response["delivery_version"] = stored_delivery.version
            response["delivery_content_hash"] = stored_delivery.content_hash
        return jsonify(response), 201

    @blueprint.post("/api/packages/<package_id>/reconcile")
    def reconcile(package_id: str):
        tenant_id, error = tenant_or_error()
        if error:
            return error
        if not hasattr(workspace, "load_delivery") or not hasattr(workspace, "save_delivery"):
            return jsonify({"error": "persistent delivery workspace required"}), 409
        existing = workspace.load_delivery(tenant_id=tenant_id, package_id=package_id)
        if existing is None:
            return jsonify({"error": "not found"}), 404
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "JSON object required"}), 400
        try:
            record, reconciliation = reconcile_payload(body)
            frozen = existing.payload.get("forecast")
            if not isinstance(frozen, dict):
                raise ValueError("stored delivery has no frozen forecast")
            _assert_frozen_forecast(record, frozen)
            updated_payload = dict(existing.payload)
            updated_payload["outcome"] = {
                "identity": {
                    "case_id": record.case_id,
                    "source_platform": record.source_platform,
                    "destination_platform": record.destination_platform,
                    "workload_class": record.workload_class,
                    "migration_strategy": record.migration_strategy,
                },
                "reconciliation": _json_safe(asdict(reconciliation)),
            }
            stored_delivery = workspace.save_delivery(
                tenant_id=tenant_id,
                package_id=package_id,
                payload=updated_payload,
            )
        except (KeyError, TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 422
        return jsonify(
            {
                "package_id": package_id,
                "delivery_version": stored_delivery.version,
                "delivery_content_hash": stored_delivery.content_hash,
                "outcome": updated_payload["outcome"],
            }
        )

    @blueprint.get("/api/packages/<package_id>")
    def get_package(package_id: str):
        tenant_id, error = tenant_or_error()
        if error:
            return error
        if hasattr(workspace, "load_delivery"):
            delivery = workspace.load_delivery(tenant_id=tenant_id, package_id=package_id)
            if delivery is not None:
                return jsonify(
                    {
                        "package_id": delivery.package_id,
                        "delivery_version": delivery.version,
                        "delivery_content_hash": delivery.content_hash,
                        "delivery": delivery.payload,
                    }
                )
        record = workspace.load(tenant_id=tenant_id, package_id=package_id)
        if record is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(
            {
                "package_id": record.package_id,
                "version": record.version,
                "content_hash": record.content_hash,
                "decision_package": _json_safe(asdict(record.payload)),
            }
        )

    return blueprint
