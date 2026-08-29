from datetime import date

from earnedcash.due_date import (
    DueDateEvidence,
    DueTruthState,
    determine_due_truth,
)


def evidence(*, due_date=date(2026, 8, 29), evidence_ref="invoice:due-date", verified=True):
    return DueDateEvidence(
        due_date=due_date,
        evidence_ref=evidence_ref,
        independently_verified=verified,
    )


def test_day_before_verified_due_date_is_not_yet_due():
    result = determine_due_truth(as_of=date(2026, 8, 28), evidence=evidence())
    assert result.state == DueTruthState.NOT_YET_DUE
    assert result.due is False


def test_exact_verified_due_date_is_due():
    result = determine_due_truth(as_of=date(2026, 8, 29), evidence=evidence())
    assert result.state == DueTruthState.DUE
    assert result.due is True


def test_day_after_verified_due_date_is_due():
    result = determine_due_truth(as_of=date(2026, 8, 30), evidence=evidence())
    assert result.state == DueTruthState.DUE
    assert result.due is True


def test_unverified_due_date_is_unknown():
    result = determine_due_truth(
        as_of=date(2026, 8, 30), evidence=evidence(verified=False)
    )
    assert result.state == DueTruthState.UNKNOWN
    assert result.due is None
    assert result.reason == "DUE_DATE_EVIDENCE_NOT_VERIFIED"


def test_missing_due_date_is_unknown():
    result = determine_due_truth(
        as_of=date(2026, 8, 30), evidence=evidence(due_date=None)
    )
    assert result.state == DueTruthState.UNKNOWN
    assert result.due is None
    assert result.reason == "DUE_DATE_MISSING"


def test_missing_evidence_reference_is_unknown():
    result = determine_due_truth(
        as_of=date(2026, 8, 30), evidence=evidence(evidence_ref="")
    )
    assert result.state == DueTruthState.UNKNOWN
    assert result.due is None
    assert result.reason == "DUE_DATE_EVIDENCE_REFERENCE_MISSING"


def test_same_as_of_and_evidence_is_deterministic():
    first = determine_due_truth(as_of=date(2026, 8, 29), evidence=evidence())
    second = determine_due_truth(as_of=date(2026, 8, 29), evidence=evidence())
    assert first == second
