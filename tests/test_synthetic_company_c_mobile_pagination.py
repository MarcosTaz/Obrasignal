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
    assert re.search(r"api\.opportunities\(\{[^}]*q:search[^}]*minscore:criteria\.minScore[^}]*openOnly:criteria\.openOnly[^}]*limit:80,offset", APP)
    assert re.search(r"setItems\(current=>\{const merged=Array\.from\(new Map", APP)
    assert 'setPage(nextPage)' in APP


def test_fresh_filter_or_manual_refresh_resets_to_first_page():
    assert 'const onRefresh=()=>load({manual:true,offset:0})' in APP
    assert 'const submitSearch=()=>load({manual:true,offset:0})' in APP
    assert 'load({manual:true,criteria,offset:0})' in APP


def test_load_more_uses_server_next_offset_and_has_explicit_loading_state():
    assert 'if(moreLoading||!page?.has_more||page?.next_offset==null)return' in APP
    assert 'offset:page.next_offset,append:true' in APP
    assert "moreLoading?'A carregar…':'Carregar mais oportunidades'" in APP
