from storage_contract import (
    KNOWN_TABLE_OWNERS,
    PREBUILD_CONTRACTS,
    STARTUP_CONTRACTS,
    RUNTIME_CONTRACTS,
    TEST_ONLY_CONTRACTS,
    contract_fingerprint,
)


def test_e2e_fixture_is_explicitly_owned_but_test_only():
    contract = TEST_ONLY_CONTRACTS["e2e_opportunity_fixtures"]
    assert contract.owner == "E2E fixture / e2e_fixture_api [TEST_ONLY]"
    assert contract.tenant_column == "account_id"
    assert "e2e_opportunity_fixtures" in KNOWN_TABLE_OWNERS
    assert "e2e_opportunity_fixtures" not in STARTUP_CONTRACTS
    assert "e2e_opportunity_fixtures" not in RUNTIME_CONTRACTS
    assert "e2e_opportunity_fixtures" not in PREBUILD_CONTRACTS


def test_test_only_fixture_registration_does_not_change_canonical_or_prebuild_fingerprint():
    canonical = contract_fingerprint(include_runtime=True, include_prebuild=False)
    with_prebuild = contract_fingerprint(include_runtime=True, include_prebuild=True)
    assert canonical != with_prebuild
    assert "e2e_opportunity_fixtures" not in STARTUP_CONTRACTS
    assert "e2e_opportunity_fixtures" not in PREBUILD_CONTRACTS
