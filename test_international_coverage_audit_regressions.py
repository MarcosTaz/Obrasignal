import international_coverage_audit as audit


def _rows():
    return {row["ISO3"]: row for row in audit.run_audit()["countries"]}


def test_base_does_not_match_database_test_files():
    portugal = _rows()["PRT"]
    paths = portugal["PROVENANCE"]["matched_test_files"]
    assert not any("database" in path.lower() for path in paths)


def test_every_gated_build_or_shared_market_has_a_reason():
    for row in audit.run_audit()["countries"]:
        if row["MARKET_CLASSIFICATION"] in {"BUILD", "SHARED"} and row["GATED"]:
            assert row["KNOWN_GAPS"]


def test_nonproduction_build_or_shared_market_is_in_missing_integrations():
    result = audit.run_audit()
    missing = set(result["missing_integrations"])
    for row in result["countries"]:
        if row["MARKET_CLASSIFICATION"] in {"BUILD", "SHARED"} and not row["PRODUCTION_PATH"]:
            assert "NO_ACTIVE_PRODUCTION_SOURCE" in row["KNOWN_GAPS"]
            assert f"{row['COUNTRY']}:no_active_production_source" in missing
