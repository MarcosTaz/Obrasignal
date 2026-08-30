from pathlib import Path


APP = Path('mobile/App.js').read_text(encoding='utf-8')
DETAIL = Path('mobile/components/OpportunityExplanation.js').read_text(encoding='utf-8')


def test_saved_opportunities_have_a_customer_access_surface_not_only_detail_toggle():
    assert 'api.savedOpportunities(' in APP or 'api.savedOpportunities(' in DETAIL
    assert 'Guardadas' in APP or 'Ver guardadas' in DETAIL


def test_watchlist_surface_handles_loading_failure_empty_and_items_truthfully():
    source = APP if 'api.savedOpportunities(' in APP else DETAIL
    assert 'A carregar' in source
    assert 'Não foi possível' in source
    assert 'Nenhuma oportunidade guardada' in source
    assert 'opportunity_id' in source


def test_watchlist_surface_can_traverse_more_than_one_server_page():
    source = APP if 'api.savedOpportunities(' in APP else DETAIL
    assert 'offset' in source
    assert 'Carregar mais' in source
