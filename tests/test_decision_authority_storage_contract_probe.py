from storage_contract import REGISTERED_ADDITIVE_MIGRATIONS, STARTUP_CONTRACTS


def test_decision_authority_columns_are_owned_by_canonical_storage_contract():
    required = STARTUP_CONTRACTS["opportunity_decisions"].required_columns
    assert "profile_fingerprint" in required
    assert "opportunity_fingerprint" in required

    migrations = set(REGISTERED_ADDITIVE_MIGRATIONS["opportunity_decisions"])
    assert {"profile_fingerprint", "opportunity_fingerprint"} <= migrations
