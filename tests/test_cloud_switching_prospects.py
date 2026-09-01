import pytest

from cloud_switching.prospects import (
    Challengeability,
    ProspectEvidence,
    ProspectStage,
    TriState,
    qualify,
)


def test_unknowns_do_not_score_as_yes():
    result = qualify(
        ProspectEvidence(
            organization="LapIT Oy",
            stage=ProspectStage.PRE_DECISION,
            decision_within_12_months=TriState.YES,
            multiple_credible_alternatives=TriState.YES,
            challengeability=Challengeability.EXPLICIT_ALTERNATIVES,
        )
    )
    assert result.score == 35
    assert result.challengeability_overlay == 15
    assert result.research_priority == 50
    assert result.tier == "HOLD"
    assert "willing_to_freeze_forecast" in result.unknown_fields
    assert "billing_baseline_accessible" in result.unknown_fields


def test_mechanical_renewal_gets_no_challengeability_bonus():
    result = qualify(
        ProspectEvidence(
            organization="City renewal",
            stage=ProspectStage.RENEWAL_OPEN,
            decision_within_12_months=TriState.YES,
            challengeability=Challengeability.MECHANICAL_RENEWAL,
        )
    )
    assert result.score == 20
    assert result.challengeability_overlay == 0
    assert result.research_priority == 20


def test_structure_under_review_gets_research_overlay_without_inflating_canonical_score():
    result = qualify(
        ProspectEvidence(
            organization="District IT",
            stage=ProspectStage.PRE_DECISION,
            decision_within_12_months=TriState.YES,
            challengeability=Challengeability.STRUCTURE_UNDER_REVIEW,
        )
    )
    assert result.score == 20
    assert result.challengeability_overlay == 10
    assert result.research_priority == 30


def test_completed_case_is_capped_for_acquisition_research():
    result = qualify(
        ProspectEvidence(
            organization="Completed migration",
            stage=ProspectStage.COMPLETED,
            decision_within_12_months=TriState.YES,
            material_estate=TriState.YES,
            multiple_credible_alternatives=TriState.YES,
            original_business_case_preserved=TriState.YES,
            billing_baseline_accessible=TriState.YES,
            telemetry_estate_evidence_accessible=TriState.YES,
            finops_finance_involved=TriState.YES,
            challengeability=Challengeability.EXPLICIT_ALTERNATIVES,
        )
    )
    assert result.score == 90
    assert result.research_priority == 35


def test_public_completed_case_cannot_claim_willingness_to_freeze_forecast():
    with pytest.raises(ValueError, match="cannot prove willingness"):
        qualify(
            ProspectEvidence(
                organization="Completed migration",
                stage=ProspectStage.COMPLETED,
                willing_to_freeze_forecast=TriState.YES,
            )
        )
