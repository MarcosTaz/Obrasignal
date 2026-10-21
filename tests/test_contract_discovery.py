from contract_discovery import (
    account_profile_mutation_matrix,
    observe_account_profile,
    observe_mobile_unknown_coercions,
)


def test_account_profile_is_discovered_not_enrolled_or_false_green():
    observed = observe_account_profile()
    assert observed["contract"] == "account_profile.v1"
    assert observed["status"] == "DISCOVERED_UNKNOWN"
    assert observed["producer"]["get"] == "profile_envelope"
    assert observed["producer"]["post"] == "save_profile_envelope"
    assert observed["consumer"]["parser"] == "truthy_envelope_or_flat"
    assert observed["risk"] == "PROFILE_CONTRACT_REVIEW_REQUIRED"


def test_account_profile_truthiness_matrix_keeps_null_absent_malformed_unproven():
    matrix = account_profile_mutation_matrix()
    assert matrix["normal_envelope"] == "PROFILE_OBJECT"
    assert matrix["profile_empty_object"] == "PROFILE_OBJECT"
    assert matrix["profile_null"] == "ENVELOPE_MISINTERPRETED_AS_PROFILE"
    assert matrix["profile_absent"] == "ENVELOPE_MISINTERPRETED_AS_PROFILE"
    assert matrix["legacy_flat_profile"] == "FLAT_PROFILE_ACCEPTED"
    assert matrix["future_additive_envelope"] == "PROFILE_OBJECT"
    assert matrix["malformed_truthy_profile"] == "MALFORMED_PROFILE_ACCEPTED_BY_UNWRAP"


def test_mobile_unknown_coercions_are_explicit_discovered_breaking_debt():
    findings = {item["id"]: item for item in observe_mobile_unknown_coercions()}

    assert findings["mobile.stats.rejected_to_zero"]["coercion"] == "UNKNOWN_TO_ZERO"
    assert findings["mobile.opportunity.missing_source_to_ted"]["coercion"] == "UNKNOWN_TO_TED"
    assert findings["mobile.opportunity.missing_score_to_zero"]["coercion"] == "UNKNOWN_TO_ZERO"
    assert findings["mobile.opportunity.missing_reason_fabricated"]["coercion"] == "UNKNOWN_TO_POSITIVE_EXPLANATION"
    assert findings["mobile.workflow.missing_status_to_new"]["coercion"] == "UNKNOWN_TO_NEW"
    assert all(item["status"] == "DISCOVERED_BREAKING" for item in findings.values())
