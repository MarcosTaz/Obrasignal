from datetime import datetime, timezone
import sqlite3

import pytest

from capability_registry import capability, enabled_capabilities
from contract_expiry import evaluate_contract_expiry
from procurement_lineage import detect_lineage_relations, ensure_lineage_tables
from procurement_milestones import DatePrecision, normalize_milestones, temporal_status
from procurement_plan_intelligence import normalize_procurement_plan, plan_read_model


def test_contract_expiry_remains_research_gated():
    spec = capability("CONTRACT_EXPIRY")
    assert spec.state == "RESEARCH"
    assert spec.dependencies == ("SIGNAL",)
    assert spec.feature_flag == "contract_expiry_signals_v0"
    assert "CONTRACT_EXPIRY" not in enabled_capabilities()


def test_plan_never_becomes_live_tender_or_exact_deadline():
    plan = normalize_procurement_plan({
        "source": "PLAN",
        "signal_type": "PROCUREMENT_PLAN",
        "external_id": "p-1",
        "title": "School rehabilitation",
        "buyer": "Municipality",
        "source_reference": "PLAN-77",
        "planned_procurement_date": "Q3 2027",
        "value": "500000",
        "currency": "EUR",
        "official_source": True,
    })
    view = plan_read_model(plan)
    assert plan.planned_procurement_date.precision == "QUARTER"
    assert plan.planned_procurement_date.exact_date is None
    assert view["deadline"] is None
    assert view["is_open_tender"] is False
    assert view["value_semantics"] == "ESTIMATED"


def test_milestone_date_and_timezone_precision_are_not_invented():
    date_only = normalize_milestones({"external_id": "t-1", "deadline": "2027-03-31"})[0]
    naive_time = normalize_milestones({"external_id": "t-2", "deadline": "2027-03-31T17:00:00"})[0]
    quarter = normalize_milestones({
        "external_id": "t-3",
        "milestones": [{"type": "EXPECTED_CONTRACT_START", "value": "Q3 2027"}],
    })[0]
    assert date_only.temporal.precision is DatePrecision.DATE
    assert "T" not in date_only.temporal.value
    assert naive_time.temporal.timezone_name is None
    assert temporal_status(naive_time, now=datetime(2027, 3, 20, 12, tzinfo=timezone.utc)) == "UNKNOWN"
    assert quarter.temporal.precision is DatePrecision.QUARTER
    assert quarter.temporal.value == "Q3 2027"


def test_weak_similarity_never_confirms_procurement_lineage():
    tender = {
        "source": "A", "external_id": "t", "signal_type": "TENDER",
        "title": "Road works", "buyer_id": "buyer-1", "country": "PT",
    }
    award = {
        "source": "B", "external_id": "a", "signal_type": "AWARD",
        "title": "Road works", "buyer_id": "buyer-1", "country": "PT",
    }
    result = detect_lineage_relations([tender, award])
    assert result["confirmed_relations"] == []
    assert result["candidates"]
    assert all(item["status"] == "UNRESOLVED" for item in result["candidates"])


def test_lineage_schema_is_additive_and_idempotent():
    conn = sqlite3.connect(":memory:")
    ensure_lineage_tables(conn)
    ensure_lineage_tables(conn)
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"procurement_lineage_nodes", "procurement_lineage_edges"} <= names


def test_award_cannot_masquerade_as_contract_for_expiry():
    with pytest.raises(ValueError, match="contract_id"):
        evaluate_contract_expiry(
            {"signal_type": "AWARD", "external_id": "award-1", "award_date": "2026-01-01"},
            datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
        )


def test_contract_expiry_never_confirms_replacement_or_exercises_option():
    assessment = evaluate_contract_expiry({
        "signal_type": "CONTRACT",
        "external_id": "c-1",
        "contract_id": "c-1",
        "contract_status": "ACTIVE",
        "contract_end_date": "2027-01-01",
        "option_periods": [{"months": 12}],
        "source_reference": "contract-register:c-1",
    }, datetime(2026, 8, 25, 12, tzinfo=timezone.utc))
    record = assessment.as_signal_record()
    assert assessment.current_known_end == "2027-01-01"
    assert assessment.extension_status == "OPTION_EXISTS_NOT_EXERCISED"
    assert record["signal_type"] == "CONTRACT_EXPIRY"
    assert record["is_open_tender"] is False
    assert record["replacement_procurement_confirmed"] is False
