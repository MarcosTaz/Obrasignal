from pathlib import Path

SURFACE = Path('mobile/components/AccountPrivacyControls.js')


def test_accepted_product_private_deletion_purges_device_private_tenant_state():
    source = SURFACE.read_text(encoding='utf-8')

    assert "import { storage } from '../src/storage'" in source
    assert 'next?.product_private_db_deleted === true' in source
    assert 'await storage.bindPrivateTenant(null)' in source


def test_accepted_deletion_ends_authenticated_product_session_after_local_purge_attempt():
    source = SURFACE.read_text(encoding='utf-8')

    assert "import { supabase } from '../lib/supabase'" in source
    assert 'await supabase.auth.signOut()' in source
    assert 'finally' in source


def test_local_cleanup_failure_is_not_reported_as_completed():
    source = SURFACE.read_text(encoding='utf-8')

    assert 'Não foi possível confirmar a limpeza privada local deste dispositivo.' in source
    assert 'A revogação externa continua pendente.' in source
