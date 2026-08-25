from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_watchlist_and_readiness_mobile_surfaces_survive_semantic_union():
    component = (ROOT / "mobile" / "components" / "OpportunityExplanation.js").read_text(encoding="utf-8")
    api = (ROOT / "mobile" / "src" / "api.js").read_text(encoding="utf-8")
    assert "SavedOpportunityControl" in component
    assert "ReadinessChecklist" in component
    assert "api.saveOpportunity" in component
    assert "api.readiness" in component
    assert "saveOpportunity:" in api
    assert "readiness:(id)" in api


def test_readiness_status_color_uses_defined_tone_regression_guard():
    component = (ROOT / "mobile" / "components" / "OpportunityExplanation.js").read_text(encoding="utf-8")
    assert "const tone=toneForStatus(status)" in component
    assert "{color:tone}" in component
    assert "{ color }" not in component
