from factory_cloud.pilot_contract import load_pilot_contract


def test_industrial_claims_pilot_is_assisted_fail_closed_and_commercially_unproven():
    pilot = load_pilot_contract("vertical_apps/industrial_claims/pilot.json")
    assert pilot["schema_version"] == 5
    assert pilot["vertical"] == "industrial-claims"
    assert pilot["production_authority"] is False
    assert pilot["pricing"]["status"] == "HYPOTHESIS"
    assert pilot["commercial_success"]["status"] == "UNPROVEN"
    assert "claim_currency" in pilot["required_inputs"]

    evidence = pilot["evidence_policy"]
    assert evidence["reference_only_is_review_ready"] is False
    assert evidence["document_content_hashed"] is True
    assert evidence["raw_document_content_persisted_by_service"] is False
    assert evidence["individual_document_content_limit_bytes"] == 1_000_000
    assert evidence["recovered_or_closed_outcome_requires_document_content"] is True
    assert evidence["outcome_document_and_state_persist_atomically"] is True

    economic = pilot["economic_lineage"]
    assert economic["currency_required_for_review_ready"] is True
    assert economic["currency_normalized_uppercase"] is True
    assert economic["recovery_currency_must_match_reviewed_currency"] is True
    assert economic["currency_conversion_implemented"] is False

    identity = pilot["identity_authorization"]
    assert identity["source"] == "verified_provider_identity"
    assert identity["raw_identity_headers_authoritative"] is False
    assert identity["roles"] == {"analyze": "analyst", "review": "reviewer", "action": "operator", "resolve": "operator"}
    assert identity["four_eyes_review_required"] is True
    assert identity["admin_may_self_review"] is False

    required_fail_closed = {
        "cost_without_commercial_basis",
        "reference_only_documentary_evidence",
        "unknown_notice_deadline",
        "missing_claim_currency",
        "invalid_claim_currency",
        "recovery_currency_mismatch",
        "missing_outcome_documentary_evidence",
        "outcome_evidence_collision",
        "non_finite_economic_input",
        "recovery_exceeds_reviewed_net_potential",
        "duplicate_success_fee",
        "unverified_identity",
        "tenant_identity_mismatch",
        "missing_required_role",
        "self_review",
        "partial_case_persistence",
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
        "currency_lineage_green",
        "outcome_evidence_lineage_green",
        "role_authorization_green",
        "four_eyes_green",
        "operation_audit_green",
        "atomic_persistence_green",
        "tenant_scoped_role_queue_green",
        "operator_console_green",
        "browser_security_green",
        "runtime_provisioned",
        "provider_role_mapping_verified",
        "pricing_validated_or_revised",
    }
    assert required_exit <= set(pilot["pilot_exit_criteria"])
