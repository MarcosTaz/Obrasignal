from global_market_discovery_evidence import DISCOVERY_EVIDENCE, SERBIA, TURKEY


def test_discovery_evidence_never_promotes_outside_135_candidates():
    assert set(DISCOVERY_EVIDENCE) == {"Turkey", "Serbia"}
    assert {record.state for record in DISCOVERY_EVIDENCE.values()} <= {"DISCOVERED", "RESEARCHING"}


def test_turkey_public_access_is_not_machine_or_legal_green():
    assert TURKEY.state == "RESEARCHING"
    assert TURKEY.legal_state == "LEGAL_UNKNOWN"
    assert TURKEY.technical_state == "TECHNICAL_BLOCKED"
    assert "interactive question/number challenge" in TURKEY.source_observation
    assert "must not be bypassed" in TURKEY.exact_gap


def test_serbia_current_portal_does_not_inherit_stale_old_open_data():
    assert SERBIA.state == "RESEARCHING"
    assert SERBIA.legal_state == "LEGAL_UNKNOWN"
    assert SERBIA.technical_state == "TECHNICAL_UNKNOWN"
    assert "2020" in SERBIA.source_observation
    assert "stale" in SERBIA.exact_gap


def test_free_access_is_not_treated_as_commercial_reuse_evidence():
    assert "does not" in TURKEY.commercial_observation
    assert "does not" in SERBIA.commercial_observation
