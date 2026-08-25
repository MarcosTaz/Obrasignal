import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "acceptance" / "account_lifecycle.json"


def _contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_account_lifecycle_is_explicitly_unproven_not_false_ready():
    data = _contract()
    assert data["status"] == "IMPLEMENTATION_MISSING_OR_UNPROVEN"
    assert data["handoff_required"] is True
    assert set(data["contracts"]) == {"PASSWORD_RECOVERY", "DATA_EXPORT", "ACCOUNT_DELETION"}


def test_password_recovery_keeps_provider_and_tenant_authority_boundaries():
    contract = _contract()["contracts"]["PASSWORD_RECOVERY"]
    assert contract["implementation_state"] == "MISSING_CUSTOMER_SURFACE"
    assert "recovery_does_not_bypass_provider_authentication" in contract["expected_truths"]
    assert "successful_recovery_does_not_change_tenant_identity" in contract["expected_truths"]
    assert "client_selected_account_becomes_authority" in contract["forbidden_claims"]


def test_export_is_tenant_scoped_and_never_claims_unproven_completeness():
    contract = _contract()["contracts"]["DATA_EXPORT"]
    assert "export_never_includes_other_tenant_private_state" in contract["expected_truths"]
    assert "export_does_not_claim_completeness_for_data_the_product_does_not_own" in contract["expected_truths"]
    assert "export_includes_secrets_or_provider_credentials" in contract["forbidden_claims"]


def test_deletion_requires_proven_postconditions_without_destroying_shared_public_facts():
    contract = _contract()["contracts"]["ACCOUNT_DELETION"]
    expected = set(contract["expected_truths"])
    forbidden = set(contract["forbidden_claims"])
    assert "deleted_account_cannot_continue_reading_or_writing_private_state" in expected
    assert "one_tenant_deletion_never_deletes_another_tenant_private_state" in expected
    assert "tenant_exit_does_not_silently_delete_shared_public_procurement_facts" in expected
    assert "account_deleted_when_cleanup_failed" in forbidden
    assert "deletion_success_without_postcondition_proof" in forbidden


def test_account_lifecycle_contract_makes_no_legal_compliance_claim():
    boundary = _contract()["legal_boundary"]
    assert "does not assert GDPR" in boundary
