from factory_cloud.pilot_contract import load_pilot_contract


def test_industrial_claims_pilot_is_assisted_fail_closed_and_commercially_unproven():
    pilot = load_pilot_contract("vertical_apps/industrial_claims/pilot.json")
    assert pilot["schema_version"] == 10
    assert pilot["vertical"] == "industrial-claims"
    assert pilot["production_authority"] is False
    assert pilot["pricing"]["status"] == "HYPOTHESIS"
    assert pilot["commercial_success"]["status"] == "UNPROVEN"
    assert "claim_currency" in pilot["required_inputs"]
    assert "notice_deadline_or_declared_none_for_review" in pilot["required_inputs"]

    evidence = pilot["evidence_policy"]
    assert evidence["reference_only_is_review_ready"] is False
    assert evidence["document_content_hashed"] is True
    assert evidence["raw_document_content_persisted_by_service"] is False
    assert evidence["individual_document_content_limit_bytes"] == 1_000_000
    assert evidence["recovered_or_closed_outcome_requires_document_content"] is True
    assert evidence["outcome_document_and_state_persist_atomically"] is True

    pre_review = pilot["pre_review_entitlement_policy"]
    assert pre_review == {
        "documentary_complete_confidence": "PARTIAL",
        "missing_evidence_confidence": "UNRESOLVED",
        "generic_actionable_before_human_review": False,
        "ready_for_review_is_documentary_workflow_state": True,
        "review_approval_is_legal_conclusion": False,
        "recoverability_established_before_external_evidence": False,
        "rule_ref": "documented-commercial-basis-v3-pre-review",
    }

    review = pilot["review_workflow_policy"]
    assert review == {
        "approval_scope": "INTERNAL_WORKFLOW_APPROVAL",
        "approval_is_legal_conclusion": False,
        "approval_establishes_recoverability": False,
        "approval_authorizes_customer_contact": False,
        "approval_authorizes_external_claim_submission": False,
        "independent_reviewer_required": True,
        "decision_reason_required": True,
    }

    notice = pilot["notice_truth_policy"]
    assert notice == {
        "unknown_fails_closed": True,
        "analyst_date_state": "DECLARED_DATE_FOR_REVIEW",
        "analyst_no_deadline_state": "DECLARED_NONE_FOR_REVIEW",
        "independent_review_required": True,
        "software_pre_review_verification_claimed": False,
    }

    bounds = pilot["input_bounds"]
    assert bounds == {
        "tenant_id_max_chars": 64,
        "case_and_outcome_reference_max_chars": 512,
        "finding_id_max_chars": 2048,
        "actor_id_max_chars": 256,
        "review_reason_max_chars": 4000,
        "missing_evidence_max_items": 100,
        "missing_evidence_key_max_chars": 128,
        "finding_queue_max_items": 100,
        "amount_text_max_chars": 128,
        "amount_significant_digits_max": 50,
        "amount_integer_digits_max": 36,
        "amount_decimal_places_max": 18,
        "amount_absolute_exponent_max": 36,
    }

    collision = pilot["identity_collision_policy"]
    assert collision == {
        "tenant_matches_provider_account_contract": True,
        "contract_reference_is_structured_not_delimiter_concatenated": True,
        "shared_store_outcome_id_is_tenant_scoped": True,
    }

    dossier = pilot["dossier_lineage"]
    assert dossier["case_metadata_atomic_with_case"] is True
    assert dossier["entitlement_evidence_must_match_finding"] is True
    assert dossier["calculation_evidence_must_be_within_finding"] is True
    assert dossier["deadline_evidence_must_be_within_finding"] is True
    assert dossier["recovery_fingerprint_event_must_match_case"] is True
    assert dossier["creation_audit_must_be_unique"] is True
    assert dossier["outcome_evidence_type_must_match"] is True
    assert dossier["corrupt_or_ambiguous_lineage_fails_closed"] is True

    backup = pilot["backup_restore_policy"]
    assert backup == {
        "sqlite_integrity_check_required": True,
        "case_metadata_preserved": True,
        "recovery_index_preserved": True,
        "finding_and_audit_lineage_preserved": True,
        "outcome_and_outcome_evidence_preserved": True,
        "tenant_isolation_preserved": True,
        "raw_document_content_absent_after_restore": True,
    }

    economic = pilot["economic_lineage"]
    assert economic["currency_required_for_review_ready"] is True
    assert economic["currency_normalized_uppercase"] is True
    assert economic["recovery_currency_must_match_reviewed_currency"] is True
    assert economic["currency_conversion_implemented"] is False
    assert economic["numeric_capacity_is_system_safety_not_business_entitlement_cap"] is True

    identity = pilot["identity_authorization"]
    assert identity["source"] == "verified_provider_identity"
    assert identity["raw_identity_headers_authoritative"] is False
    assert identity["roles"] == {"analyze": "analyst", "review": "reviewer", "action": "operator", "resolve": "operator"}
    assert identity["four_eyes_review_required"] is True
    assert identity["admin_may_self_review"] is False

    required_fail_closed = {
        "cost_without_commercial_basis",
        "reference_only_documentary_evidence",
        "unresolved_entitlement_basis",
        "pre_review_entitlement_supported_overclaim",
        "review_scope_overclaim",
        "unknown_notice_deadline",
        "pre_review_notice_verification_overclaim",
        "missing_claim_currency",
        "invalid_claim_currency",
        "recovery_currency_mismatch",
        "missing_outcome_documentary_evidence",
        "outcome_evidence_collision",
        "cross_tenant_outcome_id_collision",
        "ambiguous_contract_reference",
        "oversized_tenant_identifier",
        "oversized_case_or_outcome_reference",
        "oversized_finding_identifier",
        "oversized_actor_identifier",
        "oversized_review_reason",
        "oversized_missing_evidence_collection",
        "numeric_input_capacity_exceeded",
        "dossier_lineage_mismatch",
        "incomplete_backup_restore",
        "non_finite_economic_input",
        "recovery_exceeds_reviewed_net_potential",
        "duplicate_success_fee",
        "unverified_identity",
        "tenant_identity_mismatch",
        "missing_required_role",
        "self_review",
        "partial_case_persistence",
        "partial_case_metadata_persistence",
    }
    assert required_fail_closed <= set(pilot["fail_closed"])

    operator_console = pilot["operator_console"]
    assert operator_console["status"] == "REPOSITORY_IMPLEMENTED"
    assert operator_console["external_runtime_exposure"] is False
    assert operator_console["content_security_policy_required"] is True
    assert operator_console["html_injection_renderer_forbidden"] is True
    assert operator_console["tenant_scoped_role_queue"] is True

    required_exit = {
        "canonical_source_green",
        "documentary_content_gate_green",
        "pre_review_entitlement_truth_green",
        "review_truth_green",
        "notice_truth_language_green",
        "currency_lineage_green",
        "numeric_capacity_green",
        "identity_collision_resistance_green",
        "outcome_evidence_lineage_green",
        "dossier_lineage_green",
        "bounded_input_surface_green",
        "role_authorization_green",
        "four_eyes_green",
        "operation_audit_green",
        "atomic_persistence_green",
        "case_metadata_atomicity_green",
        "full_dossier_backup_restore_green",
        "tenant_scoped_role_queue_green",
        "operator_console_green",
        "browser_security_green",
        "runtime_provisioned",
        "provider_role_mapping_verified",
        "pricing_validated_or_revised",
    }
    assert required_exit <= set(pilot["pilot_exit_criteria"])
