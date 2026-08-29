from factory_cloud.pilot_safe_matrix import assess, portfolio_matrix, required_evidence


def test_missing_evidence_blocks_pilot_safe():
    result = assess("contractcredit", set())
    assert result["classification"] == "NOT_PILOT_SAFE"
    assert result["gates"]["PS1"] == "BLOCKED"
    assert "web_complete" in result["missing_evidence"]
    assert "support_continuity" in result["missing_evidence"]


def test_all_required_pre_customer_evidence_can_reach_pilot_safe():
    result = assess("contractcredit", required_evidence())
    assert result["classification"] == "PILOT_SAFE"
    assert set(result["gates"].values()) == {"PASS"}


def test_forbidden_real_customer_token_never_helps_certification():
    evidence = required_evidence() | {"real_customer"}
    result = assess("contractcredit", evidence)
    assert result["classification"] == "NOT_PILOT_SAFE"
    assert result["forbidden_evidence_seen"] == ["real_customer"]


def test_portfolio_matrix_covers_every_registered_factory_and_defaults_fail_closed():
    matrix = portfolio_matrix()
    ids = {row["factory_id"] for row in matrix}
    assert "factory-cloud" in ids
    assert "obrasignal" in ids
    assert "contractcredit" in ids
    assert all(row["classification"] == "NOT_PILOT_SAFE" for row in matrix)
