from pathlib import Path


def test_onboarding_requires_server_readback_before_completion():
    source = Path('mobile/components/ProfileOnboarding.js').read_text(encoding='utf-8')
    assert 'const saved=await api.saveProfile(draft)' in source
    assert 'const persisted=await api.profile()' in source
    assert 'await storage.setProfile(persisted)' in source
    assert 'onComplete(persisted)' in source
    assert 'result.profile||draft' not in source


def test_profile_write_can_recover_one_expired_access_token():
    source = Path('mobile/src/api.js').read_text(encoding='utf-8')
    assert 'response.status===401 && !skipAuth && authRefreshes===0' in source
    assert "response.status===401 && method==='GET'" not in source
    assert 'authRefreshes+=1' in source
    assert 'attempt-=1; continue' in source


def test_profile_api_requires_canonical_profile_envelope():
    source = Path('mobile/src/api.js').read_text(encoding='utf-8')
    assert "Object.prototype.hasOwnProperty.call(data,'profile')" in source
    assert 'data?.profile||data||null' not in source
