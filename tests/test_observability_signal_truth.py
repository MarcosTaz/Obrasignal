from pathlib import Path

import pytest

from observability_signal_truth import (
    ComponentSignal,
    build_operability_snapshot,
    current_repository_signal_report,
    scan_health_endpoint,
    scan_worker_contract,
)


ROOT = Path(__file__).resolve().parents[1]


def test_current_health_endpoint_is_process_alive_not_readiness():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    render_source = (ROOT / "render.yaml").read_text(encoding="utf-8")

    contract = scan_health_endpoint(app_source, render_source)

    assert contract.present is True
    assert contract.semantic == "PROCESS_ALIVE"
    assert contract.unconditional_ok is True
    assert contract.db_evidence is False
    assert contract.worker_progress_evidence is False
    assert contract.render_health_check_consumer is True
    assert "FALSE_READINESS_RISK" in contract.findings


def test_current_worker_loop_is_not_progress_evidence():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    contract = scan_worker_contract(app_source)

    assert contract.present is True
    assert contract.loop_present is True
    assert contract.progress_signal_present is False
    assert contract.failure_signal_present is False
    assert "NO_PROGRESS_SIGNAL" in contract.findings
    assert "NO_FAILURE_STATE" in contract.findings


def test_missing_health_endpoint_stays_unknown():
    contract = scan_health_endpoint("def other():\n    return 1\n")

    assert contract.present is False
    assert contract.semantic == "UNKNOWN"
    assert contract.findings == ("HEALTH_ENDPOINT_MISSING",)


def test_richer_health_endpoint_requires_explicit_semantic_review():
    source = """
def health():
    conn = db()
    conn.execute('SELECT 1')
    return jsonify(ok=True, worker_state=last_progress)
"""
    contract = scan_health_endpoint(source)

    assert contract.db_evidence is True
    assert contract.worker_progress_evidence is True
    assert contract.semantic == "UNKNOWN_CONTRACT"
    assert "HEALTH_SEMANTIC_REVIEW_REQUIRED" in contract.findings


def test_critical_unknown_never_becomes_full():
    snapshot = build_operability_snapshot(
        [
            ComponentSignal("db", "HEALTHY", True, "db_probe"),
            ComponentSignal("worker", "UNKNOWN", True, "worker_progress"),
        ]
    )

    assert snapshot["overall"] == "UNKNOWN"
    assert snapshot["unknowns"] == ["worker"]


def test_critical_stale_never_becomes_healthy():
    snapshot = build_operability_snapshot(
        [
            ComponentSignal("db", "HEALTHY", True, "db_probe"),
            ComponentSignal("worker", "STALE", True, "worker_progress"),
        ]
    )

    assert snapshot["overall"] == "UNKNOWN"
    assert "worker" in snapshot["unknowns"]


def test_critical_unavailable_or_disabled_is_unavailable():
    unavailable = build_operability_snapshot(
        [ComponentSignal("db", "UNAVAILABLE", True, "db_probe")]
    )
    disabled = build_operability_snapshot(
        [ComponentSignal("db", "DISABLED", True, "db_probe")]
    )

    assert unavailable["overall"] == "UNAVAILABLE"
    assert disabled["overall"] == "UNAVAILABLE"


def test_optional_dependency_degradation_stays_visible_without_false_outage():
    snapshot = build_operability_snapshot(
        [
            ComponentSignal("db", "HEALTHY", True, "db_probe"),
            ComponentSignal("optional_provider", "DEGRADED", False, "provider_health"),
        ]
    )

    assert snapshot["overall"] == "FULL"
    assert snapshot["components"][1]["state"] == "DEGRADED"


def test_no_critical_signal_means_unknown_not_healthy():
    snapshot = build_operability_snapshot(
        [ComponentSignal("optional_provider", "HEALTHY", False, "provider_health")]
    )

    assert snapshot["overall"] == "UNKNOWN"


def test_duplicate_or_invalid_component_signals_fail_closed():
    with pytest.raises(ValueError, match="duplicate"):
        build_operability_snapshot(
            [
                ComponentSignal("db", "HEALTHY", True, "a"),
                ComponentSignal("db", "DEGRADED", True, "b"),
            ]
        )

    with pytest.raises(ValueError, match="unsupported"):
        ComponentSignal("db", "READY", True, "db_probe")


def test_repository_report_keeps_unproven_operability_gaps_unknown():
    report = current_repository_signal_report(ROOT)

    assert report["health_endpoint"]["semantic"] == "PROCESS_ALIVE"
    assert report["worker"]["progress_signal_present"] is False
    assert report["unowned_signal_gaps"] == {
        "db_readiness": "UNKNOWN",
        "dependency_aggregation": "UNKNOWN",
        "privacy_safe_correlation": "UNKNOWN",
        "alerting": "UNKNOWN",
    }
