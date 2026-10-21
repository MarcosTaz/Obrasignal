from capability_registry import capability, enabled_capabilities


def test_bangs_is_research_gated_and_not_enabled():
    spec = capability("BANGS")
    assert spec.state == "RESEARCH"
    assert spec.contract_versions == ("bangs.v0",)
    assert spec.feature_flag == "bangs_field_intelligence_v0"
    assert spec.kill_switch_required is True
    assert spec.private_data_owner == "BANGS"
    assert "BANGS" not in enabled_capabilities()
