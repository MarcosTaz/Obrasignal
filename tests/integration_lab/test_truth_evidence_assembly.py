from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

import source_runtime as runtime
from capability_registry import capability, enabled_capabilities
from capability_rollout import rollout_keys, runtime_enabled
from evidence_graph import EvidenceGraph
from opportunity_change_history import (
    build_monitored_state,
    detect_changes,
    ensure_change_history_tables,
)
from opportunity_data_quality import DataQualityPolicy, evaluate_opportunity_data_quality
from opportunity_freshness import evaluate_freshness
from procurement_lineage import detect_lineage_relations, ensure_lineage_tables
from source_health import ensure_source_health

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def _table_names(conn):
    return {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }


def test_truth_capability_maturity_remains_canonical_and_fail_closed():
    assert enabled_capabilities() == ("SIGNAL",)
    assert capability("EVIDENCE").state == "EXPERIMENT"
    assert capability("OPPORTUNITY_CHANGE_HISTORY").state == "RESEARCH"

    feature, kill = rollout_keys("EVIDENCE")
    assert runtime_enabled("EVIDENCE", environ={}) is False
    assert runtime_enabled("EVIDENCE", environ={feature: "true"}) is True
    assert runtime_enabled("EVIDENCE", environ={feature: "true", kill: "true"}) is False

    with pytest.raises(ValueError):
        EvidenceGraph("")


def test_research_change_history_is_dormant_in_real_source_runtime(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    runtime.discard_staged_source_syncs()

    def history_must_not_run(*args, **kwargs):
        raise AssertionError("RESEARCH Change History executed in canonical runtime")

    monkeypatch.setattr(runtime, "persist_change_observations", history_must_not_run)
    record = {
        "source": "TRUTH_QA_SOURCE",
        "signal_type": "TENDER",
        "external_id": "truth-1",
        "title": "Truth QA construction tender",
        "deadline": "2026-09-30T12:00:00Z",
        "source_status": "OPEN",
        "source_reference": "truth-1",
        "is_actionable": True,
        "lifecycle_status": "open",
    }
    runtime.stage_source_sync("TRUTH_QA_SOURCE", [record], "cursor-truth-1")
    result = runtime.commit_staged_source_syncs(conn)

    assert result["signal_records"] == 1
    assert "opportunity_snapshots" not in _table_names(conn)
    assert "opportunity_change_sets" not in _table_names(conn)
    assert "opportunity_changes" not in _table_names(conn)


def test_fresh_database_truth_schemas_coexist_and_reensure_idempotently():
    conn = sqlite3.connect(":memory:")
    ensure_source_health(conn)
    ensure_lineage_tables(conn)
    # Explicit direct ensure tests schema compatibility only. Canonical runtime is
    # separately proven above not to invoke Change History while it is RESEARCH.
    ensure_change_history_tables(conn)

    ensure_source_health(conn)
    ensure_lineage_tables(conn)
    ensure_change_history_tables(conn)

    tables = _table_names(conn)
    assert {
        "source_health",
        "source_cursor",
        "procurement_lineage_nodes",
        "procurement_lineage_edges",
        "opportunity_snapshots",
        "opportunity_change_sets",
        "opportunity_changes",
    } <= tables

    source_columns = {row[1] for row in conn.execute("PRAGMA table_info(source_health)")}
    assert {"last_failed", "consecutive_failures"} <= source_columns


def test_existing_legacy_source_health_migrates_additively_without_data_loss():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE source_health (
            source TEXT PRIMARY KEY,
            last_attempt TEXT,
            last_success TEXT,
            last_error TEXT,
            last_duration_ms INTEGER,
            last_found INTEGER DEFAULT 0,
            last_new_items INTEGER DEFAULT 0,
            status TEXT DEFAULT 'unknown'
        )"""
    )
    conn.execute(
        "INSERT INTO source_health(source,last_success,status) VALUES(?,?,?)",
        ("LEGACY_SOURCE", "2026-08-24T12:00:00+00:00", "healthy"),
    )
    conn.commit()

    ensure_source_health(conn)
    ensure_source_health(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(source_health)")}
    assert {"last_failed", "consecutive_failures"} <= columns
    row = conn.execute(
        "SELECT source,last_success,status,consecutive_failures FROM source_health WHERE source=?",
        ("LEGACY_SOURCE",),
    ).fetchone()
    assert row[0] == "LEGACY_SOURCE"
    assert row[1] == "2026-08-24T12:00:00+00:00"
    assert row[2] == "healthy"
    assert row[3] == 0


def test_completeness_and_freshness_are_independent_truth_dimensions():
    record = {
        "source": "TED",
        "signal_type": "TENDER",
        "external_id": "truth-complete-stale",
        "title": "Complete but old observed record",
        "buyer": "Public Buyer",
        "country": "PRT",
        "deadline": "2026-09-30T17:00:00Z",
        "value": "500000 EUR",
        "currency": "EUR",
        "description": "Construction works",
        "cpv": "45200000",
        "publication_date": "2026-08-20",
        "published_at": "2026-08-20T12:00:00+00:00",
        "url": "https://example.test/tender/truth",
        "source_updated_at": "2026-08-24T12:00:00+00:00",
        "last_observed": (NOW - timedelta(hours=4)).isoformat(),
    }
    quality = evaluate_opportunity_data_quality(
        record, {}, DataQualityPolicy(), evaluated_at=NOW
    )
    freshness = evaluate_freshness(
        record,
        {
            "last_success": (NOW - timedelta(minutes=5)).isoformat(),
            "last_attempt": (NOW - timedelta(minutes=1)).isoformat(),
            "last_failed": None,
            "consecutive_failures": 0,
        },
        now=NOW,
    )

    assert quality.completeness_ratio == 1.0
    assert not quality.missing_fields
    assert freshness.freshness_status == "STALE"
    assert freshness.source_health_status == "HEALTHY"


def test_same_stage_revision_is_change_history_not_confirmed_lineage():
    first = {
        "source": "TEST",
        "signal_type": "TENDER",
        "external_id": "t-v1",
        "ocid": "ocds-truth-1",
        "title": "Bridge works",
        "buyer": "Buyer",
        "country": "PT",
        "deadline": "2026-09-01T12:00:00Z",
    }
    second = dict(first, external_id="t-v2", deadline="2026-09-08T12:00:00Z")

    lineage = detect_lineage_relations([first, second])
    assert lineage["confirmed_relations"] == []

    before = build_monitored_state(first)
    after = build_monitored_state(second, before)
    fields = {change["field"] for change in detect_changes(before, after)}
    assert "deadline" in fields


def test_render_blueprint_preserves_auth_jwks_contract_and_disables_evidence_by_default():
    render = Path("render.yaml").read_text(encoding="utf-8")
    assert "OBRASIGNAL_JWKS_URL" not in render
    assert "OBRASIGNAL_JWT_ISSUER" in render
    assert "OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1" in render
    assert "OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1" in render
    assert render.count('value: "false"') >= 2
