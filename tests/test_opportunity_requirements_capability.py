from capability_registry import capability, enabled_capabilities


def test_requirements_remains_research_gated_and_not_enabled():
    spec = capability("REQUIREMENTS")
    assert spec.state == "RESEARCH"
    assert spec.dependencies == ("SIGNAL",)
    assert spec.feature_flag == "opportunity_requirements_v0"
    assert "REQUIREMENTS" not in enabled_capabilities()
    assert enabled_capabilities() == ("SIGNAL",)
