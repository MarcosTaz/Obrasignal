from factory_cloud.pilot_contract import load_pilot_contract


def test_industrial_claims_pilot_is_assisted_fail_closed_and_commercially_unproven():
    pilot = load_pilot_contract("vertical_apps/industrial_claims/pilot.json")
    assert pilot["schema_version"] == 2
    assert pilot["vertical"] == "industrial-claims"
    assert pilot["production_authority"] is False
    assert pilot["pricing"]["status"] == "HYPOTHESIS"
    assert pilot["commercial_success"]["status"] == "UNPROVEN"
    assert pilot["identity_authorization"]["source"] == "verified_provider_identity"
    assert pilot["identity_authorization"]["raw_identity_headers_authoritative"] is False
    assert pilot["identity_authorization"]["roles"] == {
        "analyze": "analyst",
        "review": "reviewer",
        "action": "operator",
        "resolve": "operator",
    }
    required_fail_closed = {
        "cost_without_commercial_basis",
        "unknown_notice_deadline",
        "non_finite_economic_input",
        "recovery_exceeds_reviewed_net_potential",
        "duplicate_success_fee",
        "unverified_identity",
        "tenant_identity_mismatch",
        "missing_required_role",
        "partial_case_persistence",
    }
    assert required_fail_closed <= set(pilot["fail_closed"])
    required_exit = {
        "canonical_source_green",
        "role_authorization_green",
        "atomic_persistence_green",
        "runtime_provisioned",
        "provider_role_mapping_verified",
        "pricing_validated_or_revised",
    }
    assert required_exit <= set(pilot["pilot_exit_criteria"])
