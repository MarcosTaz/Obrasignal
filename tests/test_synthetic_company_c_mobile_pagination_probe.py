from pathlib import Path
import re


API = Path('mobile/src/api.js').read_text(encoding='utf-8')
APP = Path('mobile/App.js').read_text(encoding='utf-8')


def test_mobile_opportunity_client_accepts_and_sends_offset():
    assert re.search(r"opportunities:async\(\{[^}]*offset=0", API)
    assert re.search(r"URLSearchParams\(\{[^}]*offset:String\(offset\)", API)


def test_radar_tracks_server_page_truth_and_loads_next_page():
    assert re.search(r"const\[page,setPage\]=useState", APP)
    assert 'opResult.value?.page' in APP
    assert 'const loadMore=' in APP
    assert 'page?.has_more' in APP
    assert 'page?.next_offset' in APP
    assert 'Carregar mais oportunidades' in APP


def test_load_more_preserves_filters_and_appends_without_duplicates():
    assert re.search(r"api\.opportunities\(\{[^}]*q:search[^}]*minscore:criteria\.minScore[^}]*openOnly:criteria\.openOnly[^}]*offset", APP)
    assert re.search(r"setItems\(current=>[^\n]*new Map", APP)
    assert 'setPage(nextPage)' in APP


def test_fresh_filter_or_manual_refresh_resets_to_first_page():
    assert 'offset:0' in APP
    assert re.search(r"applyCriteria=patch=>\{[^}]*load\(\{manual:true,criteria,offset:0\}\)", APP)
    assert re.search(r"submitSearch=\(\)=>load\(\{manual:true,offset:0\}\)", APP)
