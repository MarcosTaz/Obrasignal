from pathlib import Path


def test_mobile_watchlist_client_and_detail_control_are_wired_fail_visible():
    api_source = Path("mobile/src/api.js").read_text(encoding="utf-8")
    detail_source = Path("mobile/components/OpportunityExplanation.js").read_text(encoding="utf-8")

    for contract in (
        "saveOpportunity:(id)=>",
        "unsaveOpportunity:(id)=>",
        "savedOpportunity:(id)=>",
        "updateSavedOpportunity:(id,patch)=>",
        "savedOpportunities:",
    ):
        assert contract in api_source

    assert "api.saveOpportunity(item.id)" in detail_source
    assert "api.unsaveOpportunity(item.id)" in detail_source
    assert 'accessibilityLabel={label}' in detail_source
    assert 'selected: saved' in detail_source
    assert "Não foi possível guardar a oportunidade." in detail_source
    assert "Não foi possível remover das guardadas." in detail_source
    assert "setSaved(true)" in detail_source
    assert "response?.saved?.is_saved !== true" in detail_source
