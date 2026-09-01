from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .comparability import ObservationWindow
from .delivery import OutcomeReconciliation, reconcile_outcome
from .outcome import Evidence, EvidenceStrength, ForecastActual, MigrationOutcomeRecord


def _decimal(value, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a decimal value") from exc


def _optional_decimal(value, field: str):
    return None if value is None else _decimal(value, field)


def _evidence(item: dict, field: str) -> Evidence:
    evidence = item.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError(f"{field}.evidence is required")
    source_id = str(evidence.get("source_id", "")).strip()
    methodology_version = str(evidence.get("methodology_version", "")).strip()
    if not source_id or not methodology_version:
        raise ValueError(f"{field}.evidence requires source_id and methodology_version")
    return Evidence(
        source_id=source_id,
        strength=EvidenceStrength(evidence.get("strength", "unverified")),
        independent=bool(evidence.get("independent", False)),
        methodology_version=methodology_version,
    )


def _forecast_actual(item: dict, field: str) -> ForecastActual:
    if not isinstance(item, dict):
        raise ValueError(f"{field} object is required")
    return ForecastActual(
        forecast=_decimal(item.get("forecast"), f"{field}.forecast"),
        actual=_optional_decimal(item.get("actual"), f"{field}.actual"),
        evidence=_evidence(item, field),
    )


def parse_outcome(body: dict) -> tuple[MigrationOutcomeRecord, Decimal, ObservationWindow, ObservationWindow]:
    raw = body.get("outcome")
    if not isinstance(raw, dict):
        raise ValueError("outcome object is required")
    record = MigrationOutcomeRecord(
        case_id=str(raw.get("case_id", "")).strip(),
        source_platform=str(raw.get("source_platform", "")).strip(),
        destination_platform=str(raw.get("destination_platform", "")).strip(),
        workload_class=str(raw.get("workload_class", "")).strip(),
        migration_strategy=str(raw.get("migration_strategy", "")).strip(),
        migration_cost=_forecast_actual(raw.get("migration_cost"), "migration_cost"),
        duration_days=_forecast_actual(raw.get("duration_days"), "duration_days"),
        annual_run_cost=_forecast_actual(raw.get("annual_run_cost"), "annual_run_cost"),
        downtime_minutes=_forecast_actual(raw.get("downtime_minutes"), "downtime_minutes"),
        provider_incentive=_forecast_actual(raw.get("provider_incentive"), "provider_incentive"),
    )
    if not all((record.case_id, record.source_platform, record.destination_platform, record.workload_class, record.migration_strategy)):
        raise ValueError("outcome identity fields are required")

    pre = body.get("pre_observation")
    post = body.get("post_observation")
    if not isinstance(pre, dict) or not isinstance(post, dict):
        raise ValueError("pre_observation and post_observation are required")

    def window(raw_window: dict, name: str) -> ObservationWindow:
        units = raw_window.get("workload_units")
        return ObservationWindow(
            months=int(raw_window.get("months", 0)),
            workload_units=None if units is None else _decimal(units, f"{name}.workload_units"),
            service_level=raw_window.get("service_level"),
        )

    return (
        record,
        _decimal(body.get("pre_run_cost"), "pre_run_cost"),
        window(pre, "pre_observation"),
        window(post, "post_observation"),
    )


def reconcile_payload(body: dict) -> tuple[MigrationOutcomeRecord, OutcomeReconciliation]:
    record, pre_run_cost, pre_window, post_window = parse_outcome(body)
    reconciliation = reconcile_outcome(
        record,
        pre_run_cost=pre_run_cost,
        pre_window=pre_window,
        post_window=post_window,
    )
    return record, reconciliation
