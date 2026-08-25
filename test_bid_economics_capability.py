from capability_registry import capability, enabled_capabilities


def test_bid_economics_is_research_gated_and_not_enabled():
    spec = capability("BID_ECONOMICS")
    assert spec.state == "RESEARCH"
    assert spec.feature_flag == "bid_economics_v0"
    assert spec.kill_switch_required is True
    assert spec.dependencies == ("SIGNAL",)
    assert spec.private_data_owner == "BID_ECONOMICS"
    assert "BID_ECONOMICS" not in enabled_capabilities()
