from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STORAGE = ROOT / "mobile" / "src" / "storage.js"
APP = ROOT / "mobile" / "App.js"


def test_private_profile_cache_is_not_globally_addressed_without_tenant_identity():
    source = STORAGE.read_text(encoding="utf-8")
    assert "profile: '@obrasignal/v1/profile'" not in source, (
        "BUG-GP-015: private company profile cache uses one global device key. "
        "A second authenticated account can inherit the previous tenant's profile."
    )


def test_private_opportunity_cache_is_not_globally_addressed_without_tenant_identity():
    source = STORAGE.read_text(encoding="utf-8")
    assert "cache: '@obrasignal/v1/opportunities-cache'" not in source, (
        "BUG-GP-015: personalized Radar cache uses one global device key. "
        "Private cached opportunities must be tenant-bound or purged before account change."
    )


def test_signout_does_not_leave_unscoped_private_cache_for_next_account():
    app = APP.read_text(encoding="utf-8")
    storage = STORAGE.read_text(encoding="utf-8")
    unscoped_private_cache = (
        "getCache: () => readJson(KEYS.cache, null)" in storage
        or "getProfile: () => readJson(KEYS.profile, null)" in storage
    )
    direct_signout_without_cache_boundary = "onPress={()=>supabase.auth.signOut()}" in app
    assert not (unscoped_private_cache and direct_signout_without_cache_boundary), (
        "BUG-GP-015: sign-out leaves globally-addressed private profile/Radar cache in place. "
        "The next account can hydrate it before its own network refresh."
    )
