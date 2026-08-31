from pathlib import Path

STORAGE = Path('mobile/src/storage.js').read_text(encoding='utf-8')
TENANT = Path('mobile/src/tenantStorage.js').read_text(encoding='utf-8')
AUTH = Path('mobile/components/AuthGate.js').read_text(encoding='utf-8')
SMOKE = Path('mobile/smoke-detail.mjs').read_text(encoding='utf-8')


def test_current_main_private_state_is_not_global_asyncstorage():
    assert "privateStorage.getSettings(activePrivateTenant)" in STORAGE
    assert "privateStorage.setSettings(requirePrivateTenant(), settings)" in STORAGE
    assert "privateStorage.getCache(activePrivateTenant)" in STORAGE
    assert "privateStorage.getProfile(activePrivateTenant)" in STORAGE
    assert "readJson(KEYS.settings" not in STORAGE
    assert "AsyncStorage.setItem(KEYS.settings" not in STORAGE


def test_auth_gate_binds_supabase_user_before_private_shell():
    assert "nextState.session?.user?.id" in AUTH
    assert "await storage.bindPrivateTenant(identity)" in AUTH
    assert "authState.status === 'signed-in' && !privateReady" in AUTH


def test_tenant_storage_purges_legacy_and_validates_envelope_identity():
    assert "'@obrasignal/v1/settings'" in TENANT
    assert "envelope.identity !== tenant" in TENANT
    assert "previous && previous !== next" in TENANT
    assert "if (previous) await purgeTenant(previous)" in TENANT


def test_dynamic_regression_is_part_of_mobile_quality_smoke():
    assert "tenant-storage-regression.mjs" in SMOKE
    assert "tenant storage dynamic regression" in SMOKE
