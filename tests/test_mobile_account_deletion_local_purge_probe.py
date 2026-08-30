from pathlib import Path

SURFACE = Path('mobile/components/AccountPrivacyControls.js')


def test_account_deletion_lifecycle_is_checked_before_private_shell_is_exposed():
    source = SURFACE.read_text(encoding='utf-8')

    assert 'const [lifecycleReady, setLifecycleReady] = useState(false)' in source
    assert 'refreshStatus({ initial: true })' in source
    assert "if (!lifecycleReady)" in source
    assert 'A confirmar o estado privado da conta…' in source
    assert 'Não foi possível confirmar o estado privado da conta.' in source


def test_non_active_deletion_states_lock_hydrated_private_shell():
    source = SURFACE.read_text(encoding='utf-8')

    assert "next?.state !== 'NONE'" in source
    assert 'setPrivacyLocked(shouldLock)' in source
    assert "privacyLocked ? <View style={styles.locked}" in source


def test_accepted_product_private_deletion_purges_device_private_tenant_state():
    source = SURFACE.read_text(encoding='utf-8')

    assert "import { storage } from '../src/storage'" in source
    assert 'next?.product_private_db_deleted === true' in source
    assert 'await storage.bindPrivateTenant(null)' in source


def test_accepted_deletion_immediately_hides_hydrated_private_shell():
    source = SURFACE.read_text(encoding='utf-8')

    assert 'const [privacyLocked, setPrivacyLocked] = useState(false)' in source
    assert 'setPrivacyLocked(true)' in source
    assert "privacyLocked ? <View style={styles.locked}" in source


def test_accepted_deletion_ends_authenticated_product_session_after_local_purge_attempt():
    source = SURFACE.read_text(encoding='utf-8')

    assert "import { supabase } from '../lib/supabase'" in source
    assert 'await supabase.auth.signOut()' in source
    assert 'if (signOutError) throw signOutError' in source
    assert 'finally' in source


def test_local_cleanup_failure_is_not_reported_as_completed():
    source = SURFACE.read_text(encoding='utf-8')

    assert 'Não foi possível confirmar a limpeza privada local deste dispositivo.' in source
    assert 'A revogação externa continua pendente.' in source
