from pathlib import Path

API = Path('mobile/src/api.js')


def test_authenticated_401_refresh_is_not_limited_to_get_requests():
    source = API.read_text(encoding='utf-8')

    # A 401 response is an authentication boundary response: the protected write
    # was not accepted. Refreshing the Supabase session and retrying once is needed
    # for profile/workflow/privacy writes to recover from an expired access token.
    assert "response.status===401 && !skipAuth && authRefreshes===0" in source
    assert "response.status===401 && method==='GET'" not in source


def test_refresh_retry_remains_single_shot_and_never_applies_to_skip_auth_requests():
    source = API.read_text(encoding='utf-8')
    assert 'let authRefreshes=0' in source
    assert 'authRefreshes===0' in source
    assert 'authRefreshes+=1' in source
    assert '!skipAuth' in source
