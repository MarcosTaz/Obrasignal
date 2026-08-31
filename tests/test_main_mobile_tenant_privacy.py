from pathlib import Path

STORAGE = Path('mobile/src/storage.js').read_text(encoding='utf-8')
TENANT = Path('mobile/src/tenantStorage.js').read_text(encoding='utf-8')
AUTH_GATE = Path('mobile/components/AuthGate.js').read_text(encoding='utf-8')


def test_all_customer_local_state_is_tenant_private_on_main():
    for kind in ('saved', 'settings', 'opportunities-cache', 'profile'):
        assert repr(kind) in TENANT.split('const PRIVATE_KINDS =', 1)[1].split('];', 1)[0]
    assert 'readJson(KEYS.saved' not in STORAGE
    assert 'readJson(KEYS.settings' not in STORAGE
    assert 'readJson(KEYS.cache' not in STORAGE
    assert 'readJson(KEYS.profile' not in STORAGE


def test_authenticated_shell_waits_for_private_tenant_binding():
    assert "import { storage } from '../src/storage'" in AUTH_GATE
    assert 'await storage.bindPrivateTenant(accountId)' in AUTH_GATE
    assert "setTenantStatus('loading')" in AUTH_GATE
    assert "tenantStatus === 'loading'" in AUTH_GATE
    assert "nextState.session?.user?.id" in AUTH_GATE
