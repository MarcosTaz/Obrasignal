from source_registry import SOURCES, production_gate_reasons


def test_paraguay_registry_does_not_claim_unimplemented_lifecycle_objects():
    source = SOURCES["PY_DNCP"]

    assert source["source_id"] == "py_dncp_api_v3"
    assert source["status"] == "ready"
    assert source["legal_reuse"] == "GREEN"
    assert source["machine_access"] == "VERIFIED"
    assert source["access"] == "api_oauth"
    assert source["adapter"] == "OCDSAPIConnector"
    assert source["signal_types"] == ("TENDER",)
    assert set(source["capabilities"]) == {"search", "incremental_sync", "detail"}

    for unimplemented in ("plans", "awards", "contracts", "amendments"):
        assert unimplemented not in source["capabilities"]
    for unimplemented_signal in ("PROCUREMENT_PLAN", "AWARD", "CONTRACT"):
        assert unimplemented_signal not in source["signal_types"]


def test_paraguay_ready_prebuild_gate_semantics_are_preserved():
    # PR #101 technically live-validated the authenticated DNCP v3 route and left
    # the source ready/disabled-by-default. This truth repair removes lifecycle
    # overclaims only; it does not silently rewrite prior access/rights proof.
    assert production_gate_reasons("PY_DNCP") == ()
