import pytest

from vertical_apps.industrial_claims.metadata_triage import (
    MetadataTriageError,
    MetadataTriageInput,
    evaluate_metadata_triage,
)


def test_strong_metadata_fit_does_not_score_recoverability_or_require_documents():
    result = evaluate_metadata_triage(
        MetadataTriageInput(
            mechanism_in_scope=True,
            customer_change_identifiable=True,
            incremental_cost_source_exists=True,
            commercial_basis_document_exists=True,
            prior_recovery_reconstructable=True,
            notice_process_known=True,
            economic_owner_named=True,
            exposure_exceeds_likely_audit_fee=True,
        )
    )
    assert result.score == 10
    assert result.qualification == "METADATA_QUALIFIED"
    assert result.recoverability_scored is False
    assert result.confidential_document_intake_required is False
    assert result.unknown_signals == ()


def test_unknowns_generate_questions_without_inventing_positive_signals():
    result = evaluate_metadata_triage(
        MetadataTriageInput(
            mechanism_in_scope=True,
            customer_change_identifiable=True,
            incremental_cost_source_exists=None,
            commercial_basis_document_exists=None,
            prior_recovery_reconstructable=False,
            notice_process_known=None,
            economic_owner_named=True,
            exposure_exceeds_likely_audit_fee=None,
        )
    )
    assert result.score == 3
    assert result.qualification == "WEAK_FIT"
    assert set(result.observed_positive_signals) == {"customer_change_identifiable", "economic_owner_named"}
    assert "incremental_cost_source_exists" in result.unknown_signals
    assert len(result.next_questions) == 4


def test_out_of_scope_mechanism_is_rejected_instead_of_expanding_factory():
    result = evaluate_metadata_triage(MetadataTriageInput(mechanism_in_scope=False))
    assert result.qualification == "NO_FIT"
    assert result.score == 0
    assert "do not widen this Factory" in result.next_questions[0]


def test_mid_score_routes_to_prequalification():
    result = evaluate_metadata_triage(
        MetadataTriageInput(
            mechanism_in_scope=True,
            customer_change_identifiable=True,
            incremental_cost_source_exists=True,
            commercial_basis_document_exists=False,
            prior_recovery_reconstructable=True,
            notice_process_known=False,
            economic_owner_named=False,
            exposure_exceeds_likely_audit_fee=False,
        )
    )
    assert result.score == 5
    assert result.qualification == "NEEDS_PREQUALIFICATION"


def test_non_boolean_triage_state_fails_closed():
    payload = MetadataTriageInput(mechanism_in_scope=True)
    object.__setattr__(payload, "customer_change_identifiable", "yes")
    with pytest.raises(MetadataTriageError, match="true, false or unknown"):
        evaluate_metadata_triage(payload)
