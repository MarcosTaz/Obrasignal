from copy import deepcopy
from datetime import datetime, timezone

import pytest

from procurement_milestones import (
    DateBasis, DatePrecision, MilestoneType, RequirementLevel, ResolutionState,
    TemporalValue, ProcurementMilestone, next_upcoming_milestone,
    normalize_milestones, resolve_current_milestones, temporal_status,
)

NOW = datetime(2027, 3, 20, 12, 0, tzinfo=timezone.utc)


def explicit(**overrides):
    row = {
        "external_id": "opp-1", "source": "TEST", "source_reference": "notice-1",
        "milestones": [{"type": "BID_SUBMISSION_DEADLINE", "value": "2027-03-31T17:00:00+01:00", "precision": "EXACT_DATETIME", "timezone": "Europe/Lisbon"}],
    }
    row.update(overrides)
    return row


def test_publication_and_exact_submission_are_distinct():
    ms = normalize_milestones({"external_id": "o", "source": "S", "publication_date": "2027-03-01", "deadline": "2027-03-31T17:00:00+01:00"})
    assert {m.milestone_type for m in ms} == {MilestoneType.PUBLICATION, MilestoneType.BID_SUBMISSION_DEADLINE}
    assert next(m for m in ms if m.milestone_type == MilestoneType.PUBLICATION).temporal.precision == DatePrecision.DATE


def test_date_only_never_invents_time():
    m = normalize_milestones({"external_id": "o", "deadline": "2027-03-31"})[0]
    assert m.temporal.precision == DatePrecision.DATE
    assert m.temporal.value == "2027-03-31"
    assert "T" not in m.temporal.value


def test_quarter_never_becomes_fake_exact_date():
    m = normalize_milestones({"external_id": "o", "milestones": [{"type": "EXPECTED_CONTRACT_START", "value": "Q3 2027"}]})[0]
    assert m.temporal.precision == DatePrecision.QUARTER
    assert m.temporal.value == "Q3 2027"


def test_month_year_approximate_and_unknown_precision():
    values = [
        {"type": "EXPECTED_AWARD", "value": "2027-03"},
        {"type": "EXPECTED_CONTRACT_START", "value": "2027"},
        {"type": "OTHER", "value": "summer 2027"},
        {"type": "UNKNOWN", "value": {"precision": "UNKNOWN"}},
    ]
    ms = normalize_milestones({"external_id": "o", "milestones": values})
    assert {m.temporal.precision for m in ms} == {DatePrecision.MONTH, DatePrecision.YEAR, DatePrecision.APPROXIMATE, DatePrecision.UNKNOWN}


def test_range_validation_and_preservation():
    m = normalize_milestones({"external_id": "o", "milestones": [{"type": "SITE_VISIT", "start": "2027-03-21", "end": "2027-03-23"}]})[0]
    assert m.temporal.precision == DatePrecision.RANGE
    with pytest.raises(ValueError):
        TemporalValue(DatePrecision.RANGE, start="2027-03-23", end="2027-03-21")


def test_invalid_impossible_date_rejected():
    with pytest.raises(ValueError):
        normalize_milestones({"external_id": "o", "deadline": "2027-02-31"})


def test_invalid_timezone_rejected():
    with pytest.raises(ValueError):
        normalize_milestones({"external_id": "o", "milestones": [{"type": "BID_SUBMISSION_DEADLINE", "value": "2027-03-31T17:00:00", "timezone": "Mars/Olympus"}]})


def test_unknown_timezone_is_not_silently_utc():
    m = normalize_milestones({"external_id": "o", "deadline": "2027-03-31T17:00:00"})[0]
    assert m.temporal.timezone_name is None
    assert temporal_status(m, now=NOW) == "UNKNOWN"


def test_london_dst_instant_is_preserved():
    m = normalize_milestones({"external_id": "o", "milestones": [{"type": "BID_SUBMISSION_DEADLINE", "value": "2027-07-01T17:00:00", "timezone": "Europe/London"}]})[0]
    assert m.temporal.timezone_name == "Europe/London"
    assert temporal_status(m, now=datetime(2027, 7, 1, 15, 30, tzinfo=timezone.utc)) == "TODAY"
    assert temporal_status(m, now=datetime(2027, 7, 1, 16, 30, tzinfo=timezone.utc)) == "PASSED"


def test_site_visit_mandatory_optional_unknown():
    mandatory = normalize_milestones({"external_id": "a", "site_visit": "2027-03-25", "site_visit_mandatory": True})[0]
    optional = normalize_milestones({"external_id": "b", "site_visit": "2027-03-25", "site_visit_mandatory": False})[0]
    unknown = normalize_milestones({"external_id": "c", "site_visit": "2027-03-25"})[0]
    assert (mandatory.requirement_level, optional.requirement_level, unknown.requirement_level) == (RequirementLevel.MANDATORY, RequirementLevel.OPTIONAL, RequirementLevel.UNKNOWN)


def test_questions_eoi_qualification_opening_validity_award_and_start_are_distinct():
    row = {"external_id": "o", "question_deadline": "2027-03-22", "eoi_deadline": "2027-03-23", "qualification_deadline": "2027-03-24", "opening_date": "2027-04-01", "bid_validity_end": "2027-06-30", "expected_award": "2027-05", "award_date": "2027-05-20", "expected_contract_start": "Q3 2027", "contract_start": "2027-08-01"}
    types = {m.milestone_type for m in normalize_milestones(row)}
    assert types == {MilestoneType.QUESTIONS_DEADLINE, MilestoneType.EOI_DEADLINE, MilestoneType.QUALIFICATION_DEADLINE, MilestoneType.BID_OPENING, MilestoneType.BID_VALIDITY_END, MilestoneType.EXPECTED_AWARD, MilestoneType.AWARD, MilestoneType.EXPECTED_CONTRACT_START, MilestoneType.CONTRACT_START}


def test_explicit_basis_native_label_and_source_provenance():
    m = normalize_milestones({"external_id": "o", "source": "TED", "source_reference": "n1", "milestones": [{"type": "EOI_DEADLINE", "value": "2027-03-25", "basis": "SOURCE_DERIVED", "native_label": "Deadline for receipt of requests to participate", "source_field": "BT-131(d)-Lot"}]})[0]
    assert m.basis == DateBasis.SOURCE_DERIVED
    assert m.native_label.startswith("Deadline for receipt")
    assert m.source == "TED" and m.source_ref == "n1"


def test_oversized_native_label_rejected():
    with pytest.raises(ValueError):
        normalize_milestones({"external_id": "o", "milestones": [{"type": "OTHER", "value": "2027-03-25", "native_label": "x" * 501}]})


def test_idempotency_and_input_not_mutated():
    row = explicit()
    before = deepcopy(row)
    a = normalize_milestones(row)
    b = normalize_milestones(row)
    assert a == b
    assert [m.fingerprint for m in a] == [m.fingerprint for m in b]
    assert row == before


def test_duplicate_same_logical_source_value_suppressed():
    item = {"type": "QUESTIONS_DEADLINE", "value": "2027-03-25", "source_field": "q"}
    ms = normalize_milestones({"external_id": "o", "source": "S", "milestones": [item, dict(item)]})
    assert len(ms) == 1


def test_supersession_preserves_history_and_selects_new_deadline():
    old = normalize_milestones({"external_id": "o", "source": "S", "source_reference": "n1", "deadline": "2027-03-31"})[0]
    new = ProcurementMilestone("new", "o", MilestoneType.BID_SUBMISSION_DEADLINE, TemporalValue(DatePrecision.DATE, value="2027-04-07"), source="S", source_ref="n2", supersedes_milestone_id=old.milestone_id)
    views = resolve_current_milestones([old, new], now=NOW)
    state = {v.milestone.milestone_id: v.resolution for v in views}
    assert state[old.milestone_id] == ResolutionState.SUPERSEDED
    assert state["new"] == ResolutionState.CURRENT


def test_contemporary_conflicting_dates_remain_unresolved():
    a = ProcurementMilestone("a", "o", MilestoneType.BID_SUBMISSION_DEADLINE, TemporalValue(DatePrecision.DATE, value="2027-03-31"), source="S1")
    b = ProcurementMilestone("b", "o", MilestoneType.BID_SUBMISSION_DEADLINE, TemporalValue(DatePrecision.DATE, value="2027-04-07"), source="S2")
    views = resolve_current_milestones([a, b], now=NOW)
    assert {v.resolution for v in views} == {ResolutionState.NEEDS_VERIFICATION}


def test_lot_deadlines_do_not_collapse():
    row = {"external_id": "o", "milestones": [
        {"type": "BID_SUBMISSION_DEADLINE", "value": "2027-03-31", "lot_id": "1"},
        {"type": "BID_SUBMISSION_DEADLINE", "value": "2027-04-07", "lot_id": "2"},
    ]}
    ms = normalize_milestones(row)
    assert {(m.lot_id, m.temporal.value) for m in ms} == {("1", "2027-03-31"), ("2", "2027-04-07")}
    assert {v.resolution for v in resolve_current_milestones(ms, now=NOW)} == {ResolutionState.CURRENT}


def test_multi_stage_eoi_does_not_replace_bid_submission():
    ms = normalize_milestones({"external_id": "o", "milestones": [
        {"type": "EOI_DEADLINE", "value": "2027-03-20", "stage": "qualification"},
        {"type": "BID_SUBMISSION_DEADLINE", "value": "2027-04-20", "stage": "final"},
    ]})
    assert {(m.milestone_type, m.stage) for m in ms} == {(MilestoneType.EOI_DEADLINE, "qualification"), (MilestoneType.BID_SUBMISSION_DEADLINE, "final")}


def test_adding_unrelated_milestone_does_not_change_resolution():
    base = normalize_milestones({"external_id": "o", "deadline": "2027-03-31"})
    extra = normalize_milestones({"external_id": "o", "site_visit": "2027-03-25"})
    before = [v for v in resolve_current_milestones(base, now=NOW) if v.milestone.milestone_type == MilestoneType.BID_SUBMISSION_DEADLINE]
    after = [v for v in resolve_current_milestones(base + extra, now=NOW) if v.milestone.milestone_type == MilestoneType.BID_SUBMISSION_DEADLINE]
    assert before == after


def test_cancelled_is_explicit_not_inferred():
    m = ProcurementMilestone("x", "o", MilestoneType.SITE_VISIT, TemporalValue(DatePrecision.DATE, value="2027-03-25"), cancelled=True)
    assert resolve_current_milestones([m], now=NOW)[0].resolution == ResolutionState.CANCELLED


def test_injected_clock_required_and_next_milestone_is_deterministic():
    with pytest.raises(ValueError):
        temporal_status(normalize_milestones({"external_id": "o", "deadline": "2027-03-31"})[0], now=datetime(2027, 3, 20))
    ms = normalize_milestones({"external_id": "o", "questions_deadline": "2027-03-22", "deadline": "2027-03-31"})
    assert next_upcoming_milestone(ms, now=NOW).milestone_type == MilestoneType.QUESTIONS_DEADLINE


def test_no_alert_or_pursuit_decision_side_effects():
    ms = normalize_milestones({"external_id": "o", "deadline": "2027-03-21"})
    assert all(not hasattr(m, "notification") and not hasattr(m, "pursuit_decision") for m in ms)
