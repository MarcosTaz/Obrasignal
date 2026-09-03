from factory_cloud.pilot_contract import load_pilot_contract


def test_industrial_claims_pilot_is_business_first_assisted_and_fail_closed():
    pilot = load_pilot_contract("vertical_apps/industrial_claims/pilot.json")

    assert pilot["schema_version"] == 16
    assert pilot["vertical"] == "industrial-claims"
    assert pilot["mode"] == "assisted"
    assert pilot["production_authority"] is False
    assert pilot["commercial_success"]["status"] == "UNPROVEN"
    assert pilot["pricing"]["status"] == "HYPOTHESIS"

    assert pilot["wedge"] == "supplier-side customer-caused engineering/change cost recovery (NRE / change-driven incremental cost)"
    focus = pilot["commercial_focus_policy"]
    assert focus == {
        "frozen_until_real_commercial_proof": True,
        "primary_claim_family": "NRE",
        "primary_case_type": "CUSTOMER_DIRECTED_ENGINEERING_CHANGE_COST",
        "secondary_capabilities_are_not_pilot_gates": True,
        "dashboard_completion_required_before_assisted_delivery": False,
        "assisted_delivery_default": True,
        "initial_paid_product": "AUDIT_GRADE_RECOVERY_DOSSIER",
        "insufficient_evidence_disposition": "NO_CLAIM_OR_NEEDS_REVIEW",
    }

    assert "claim_currency" in pilot["required_inputs"]
    assert "mitigation_and_prior_recovery" in pilot["required_inputs"]
    assert "notice_deadline_or_declared_none_for_review" in pilot["required_inputs"]

    evidence = pilot["evidence_policy"]
    assert evidence["reference_only_is_review_ready"] is False
    assert evidence["document_content_hashed"] is True
    assert evidence["raw_document_content_persisted_by_service"] is False
    assert evidence["recovered_or_closed_outcome_requires_document_content"] is True
    assert evidence["outcome_document_and_state_persist_atomically"] is True

    pre_review = pilot["pre_review_entitlement_policy"]
    assert pre_review["documentary_complete_confidence"] == "PARTIAL"
    assert pre_review["missing_evidence_confidence"] == "UNRESOLVED"
    assert pre_review["generic_actionable_before_human_review"] is False
    assert pre_review["review_approval_is_legal_conclusion"] is False
    assert pre_review["recoverability_established_before_external_evidence"] is False

    review = pilot["review_workflow_policy"]
    assert review["approval_scope"] == "INTERNAL_WORKFLOW_APPROVAL"
    assert review["approval_is_legal_conclusion"] is False
    assert review["approval_establishes_recoverability"] is False
    assert review["approval_authorizes_customer_contact"] is False
    assert review["approval_authorizes_external_claim_submission"] is False
    assert review["independent_reviewer_required"] is True

    timing = pilot["deadline_timing_policy"]
    assert timing["declared_date_timing_states"] == ["OPEN", "DUE_TODAY", "EXPIRED"]
    assert timing["expired_establishes_nonrecoverability"] is False
    assert timing["expired_requires_human_exception_or_waiver_review"] is True

    outcome = pilot["outcome_recording_policy"]
    assert outcome["api_requires_final_cumulative_confirmation"] is True
    assert outcome["installment_stream_supported"] is False
    assert outcome["recorded_amount_semantics"] == "FINAL_CUMULATIVE_OUTCOME"
    assert outcome["documentary_evidence_required"] is True

    transition = pilot["transition_integrity_policy"]
    assert transition["review_requires_valid_dossier_preflight"] is True
    assert transition["action_requires_valid_dossier_preflight"] is True
    assert transition["resolve_requires_valid_dossier_preflight"] is True
    assert transition["corrupt_dossier_blocks_state_mutation"] is True

    replay = pilot["replay_integrity_policy"]
    assert replay["validation_is_atomic"] is True
    assert replay["late_conflict_rolls_back_partial_repair"] is True
    assert replay["replay_does_not_downgrade_lifecycle_state"] is True
    assert replay["replay_conflict_fails_closed"] is True

    amendment = pilot["amendment_policy"]
    assert amendment["one_logical_recovery_fingerprint_across_revisions"] is True
    assert amendment["current_revision_only_transitionable"] is True
    assert amendment["complete_predecessor_chain_validated"] is True
    assert amendment["ambiguous_successor_fails_closed"] is True
    assert amendment["amendment_requires_fresh_independent_review"] is True
    assert amendment["amendment_after_action_or_final_outcome_forbidden"] is True
    assert amendment["raw_documents_reloaded_from_storage"] is False

    package = pilot["package_policy"]
    assert package["durable_current_revision_required"] is True
    assert package["superseded_result_export_rejected"] is True
    assert package["package_establishes_recoverability"] is False
    assert package["package_authorizes_external_action"] is False

    dossier = pilot["assisted_dossier_policy"]
    assert dossier == {
        "human_causation_assessment_required": True,
        "human_customer_responsibility_assessment_required": True,
        "prior_recovery_check_required": True,
        "notice_deadline_required_or_unknown": True,
        "raw_document_content_excluded": True,
        "customer_action_authorized_by_dossier": False,
        "external_claim_submission_authorized_by_dossier": False,
        "recoverability_established_by_dossier": False,
        "adversarial_nre_cases_minimum": 20,
    }

    identity = pilot["identity_authorization"]
    assert identity["source"] == "verified_provider_identity"
    assert identity["raw_identity_headers_authoritative"] is False
    assert identity["four_eyes_review_required"] is True
    assert identity["admin_may_self_review"] is False

    required_fail_closed = {
        "cost_without_commercial_basis",
        "reference_only_documentary_evidence",
        "unknown_notice_deadline",
        "missing_claim_currency",
        "recovery_currency_mismatch",
        "missing_outcome_documentary_evidence",
        "recovery_exceeds_reviewed_net_potential",
        "duplicate_recovery_fingerprint",
        "duplicate_success_fee",
        "unverified_identity",
        "tenant_identity_mismatch",
        "self_review",
        "stale_revision_package_export",
        "unsupported_causation_overclaim",
        "unsupported_customer_responsibility_overclaim",
        "unknown_prior_recovery_hidden",
    }
    assert required_fail_closed <= set(pilot["fail_closed"])

    exit_criteria = set(pilot["pilot_exit_criteria"])
    assert "all_claim_families_structurally_supported" not in exit_criteria
    required_business_exit = {
        "nre_customer_change_case_type_closed_end_to_end",
        "nre_adversarial_cases_20_plus_green",
        "audit_grade_assisted_dossier_green",
        "assisted_delivery_workflow_green",
        "secure_real_document_intake_path_verified",
        "pricing_tested_or_revised_with_real_market_evidence",
        "real_external_case_handled_safely",
        "paid_path_demonstrated_or_explicitly_rejected_by_market_test",
    }
    assert required_business_exit <= exit_criteria
