from datetime import datetime, timezone

import pytest

from procurement_plan_intelligence import (
    match_plan_to_tender,
    normalize_procurement_plan,
    plan_read_model,
)
from procurement_lineage import detect_lineage_relations
from contract_expiry import actionable_expiry_signal, evaluate_contract_expiry

NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)


def _plan(**overrides):
    record = {
        "source": "OFFICIAL_PLAN",
        "external_id": "PLAN-1",
        "signal_type": "PROCUREMENT_PLAN",
        "title": "Bridge rehabilitation programme",
        "buyer": "Public Works Agency",
        "planned_procurement_date": "Q3 2027",
        "estimated_value": "2500000",
        "currency": "EUR",
        "plan_status": "PLANNED",
        "official_source": True,
        "source_reference": "PROC-PLAN-77",
        "url": "https://example.test/plan/77",
    }
    record.update(overrides)
    return record


def _lineage_record(external_id, signal_type="TENDER", **extra):
    row = {
        "source": "OFFICIAL",
        "external_id": external_id,
        "signal_type": signal_type,
        "title": extra.pop("title", "Bridge rehabilitation"),
        "buyer": extra.pop("buyer", "Public Works Agency"),
        "country": "PT",
    }
    row.update(extra)
    return row


def _contract(**overrides):
    record = {
        "signal_type": "CONTRACT",
        "external_id": "CONTRACT-1",
        "contract_id": "CONTRACT-1",
        "contract_status": "ACTIVE",
        "buyer_id": "BUYER-1",
        "supplier_id": "SUPPLIER-1",
        "source_reference": "official-contract:CONTRACT-1",
        "contract_value": 5000000,
        "currency": "EUR",
    }
    record.update(overrides)
    return record


def test_procurement_plan_q3_2027_remains_partial_and_never_becomes_open_tender():
    plan = normalize_procurement_plan(_plan())
    view = plan_read_model(plan)

    assert plan.planned_procurement_date.precision == "QUARTER"
    assert plan.planned_procurement_date.raw == "Q3 2027"
    assert view["when"] == "Q3 2027"
    assert view["date_precision"] == "QUARTER"
    assert view["is_open_tender"] is False
    assert view["deadline"] is None
    assert view["value_semantics"] == "ESTIMATED"
    assert view["estimated_value"] == "2500000"
    assert "guaranteed tender" in view["uncertainty_note"]


def test_plan_and_similar_tender_do_not_link_without_official_reference():
    plan = normalize_procurement_plan(_plan(source_reference=None))
    tender = {
        "source": "OFFICIAL_TENDER",
        "external_id": "TENDER-1",
        "signal_type": "TENDER",
        "title": "Bridge rehabilitation programme",
        "buyer": "Public Works Agency",
        "value": "2500000",
    }

    assert match_plan_to_tender(plan, tender) is None


def test_plan_to_tender_requires_shared_explicit_reference():
    plan = normalize_procurement_plan(_plan(source_reference="PROC-77"))
    tender = {
        "source": "OFFICIAL_TENDER",
        "external_id": "TENDER-77",
        "signal_type": "TENDER",
        "title": "Bridge rehabilitation programme",
        "plan_reference": "PROC-77",
    }

    relation = match_plan_to_tender(plan, tender)

    assert relation is not None
    assert relation["relation"] == "PLAN_TO_TENDER"
    assert relation["reference"] == "PROC-77"
    assert relation["confidence"] == "HIGH"


def test_lineage_preserves_tender_award_contract_as_distinct_stages():
    tender = _lineage_record("T-1", "TENDER", ocid="ocds-x-77")
    award = _lineage_record("A-1", "AWARD", ocid="ocds-x-77")
    contract = _lineage_record("C-1", "CONTRACT", ocid="ocds-x-77")

    result = detect_lineage_relations([tender, award, contract])
    edges = {
        (item["from_entity_type"], item["relationship_type"], item["to_entity_type"])
        for item in result["confirmed_relations"]
    }

    assert ("TENDER", "RESULTED_IN", "AWARD") in edges
    assert ("AWARD", "CONTRACTED_AS", "CONTRACT") in edges
    assert {"TENDER", "AWARD", "CONTRACT"}.issubset(
        {item["from_entity_type"] for item in result["confirmed_relations"]}
        | {item["to_entity_type"] for item in result["confirmed_relations"]}
    )


def test_similar_titles_never_confirm_lineage():
    tender = _lineage_record("T-OLD", "TENDER", title="School roof works", procurement_reference="OLD")
    award = _lineage_record("A-NEW", "AWARD", title="School roof works", procurement_reference="NEW")

    result = detect_lineage_relations([tender, award])

    assert result["confirmed_relations"] == []


def test_contract_expiry_is_evidence_not_retender_confirmation():
    assessment = evaluate_contract_expiry(_contract(contract_end_date="2026-11-23"), NOW)
    record = assessment.as_signal_record()

    assert assessment.status == "EXPIRING"
    assert assessment.days_to_expiry == 90
    assert actionable_expiry_signal(assessment)
    assert record["signal_type"] == "CONTRACT_EXPIRY"
    assert record["is_open_tender"] is False
    assert record["replacement_procurement_confirmed"] is False
    assert record["prior_known_contract_value"] == 5000000


def test_partial_contract_end_month_does_not_fabricate_day_or_actionability():
    assessment = evaluate_contract_expiry(
        _contract(contract_end_year=2027, contract_end_month=3),
        NOW,
    )

    assert assessment.current_known_end == "2027-03"
    assert assessment.end_date_precision == "MONTH"
    assert assessment.status == "UNKNOWN"
    assert assessment.days_to_expiry is None
    assert not actionable_expiry_signal(assessment)


def test_award_cannot_masquerade_as_contract_for_expiry():
    with pytest.raises(ValueError, match="contract_id"):
        evaluate_contract_expiry(
            {
                "signal_type": "AWARD",
                "external_id": "AWARD-1",
                "award_date": "2026-01-01",
            },
            NOW,
        )


def test_same_inputs_and_clock_replay_deterministically_across_pure_contracts():
    first_plan = normalize_procurement_plan(_plan())
    second_plan = normalize_procurement_plan(_plan())
    first_expiry = evaluate_contract_expiry(_contract(contract_end_date="2027-01-01"), NOW)
    second_expiry = evaluate_contract_expiry(_contract(contract_end_date="2027-01-01"), NOW)

    assert first_plan == second_plan
    assert first_expiry == second_expiry
