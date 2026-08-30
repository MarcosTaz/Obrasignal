from pathlib import Path

STORAGE = Path('mobile/src/storage.js').read_text(encoding='utf-8')
TENANT = Path('mobile/src/tenantStorage.js').read_text(encoding='utf-8')


def test_customer_settings_are_tenant_private_not_global_asyncstorage():
    assert "getSettings: () => activePrivateTenant ? privateStorage.getSettings(activePrivateTenant)" in STORAGE
    assert "setSettings: (settings) => privateStorage.setSettings(requirePrivateTenant(), settings)" in STORAGE
    assert "readJson(KEYS.settings" not in STORAGE
    assert "AsyncStorage.setItem(KEYS.settings" not in STORAGE


def test_tenant_storage_owns_settings_and_purges_legacy_global_settings():
    assert "'settings'" in TENANT.split('const PRIVATE_KINDS =', 1)[1].split('];', 1)[0]
    assert "'@obrasignal/v1/settings'" in TENANT.split('export const LEGACY_PRIVATE_KEYS =', 1)[1].split('];', 1)[0]
    assert "getSettings: (identity) => readPrivate(identity, 'settings'" in TENANT
    assert "setSettings: (identity, settings) => writePrivate(identity, 'settings', settings)" in TENANT
