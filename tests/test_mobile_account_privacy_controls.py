from pathlib import Path
import re


API = Path('mobile/src/api.js').read_text(encoding='utf-8')
GATE = Path('mobile/components/BillingGate.js').read_text(encoding='utf-8')


def test_customer_client_exposes_authenticated_account_privacy_owner_routes():
    assert "accountExport:()=>readWhenReady('/account/export')" in API
    assert "accountDeletionStatus:()=>readWhenReady('/account/deletion')" in API
    assert re.search(r"requestAccountDeletion:\(confirmation\)=>writeWhenReady\('/account/deletion',\{method:'POST',body:JSON\.stringify\(\{confirmation\}\)\}\)", API)


def test_destructive_deletion_requires_exact_server_confirmation_literal():
    assert "const DELETE_CONFIRMATION = 'DELETE_MY_OBRASIGNAL_DATA';" in GATE
    assert "deleteConfirmation !== DELETE_CONFIRMATION" in GATE
    assert "body:JSON.stringify({confirmation})" in API
    assert "Eliminar dados privados do produto" in GATE


def test_pending_deletion_copy_does_not_overclaim_external_revocation():
    assert "isto ainda não é eliminação completa da conta" in GATE
    assert "identidade/sessões" in GATE
    assert "cache local" in GATE
    assert "billing" in GATE
    assert "Nenhum sucesso é assumido" in GATE


def test_signout_after_pending_deletion_is_explicit_customer_action():
    request_body = GATE.split('const requestDeletion = async () => {', 1)[1].split('const signOutAfterDeletion', 1)[0]
    assert 'supabase.auth.signOut' not in request_body
    assert "deletionState?.state === 'PENDING'" in GATE
    assert 'Terminar sessão neste dispositivo' in GATE
    assert 'await supabase.auth.signOut()' in GATE


def test_export_is_customer_initiated_without_console_logging_payload():
    export_body = GATE.split('const exportAccountData = async () => {', 1)[1].split('const requestDeletion', 1)[0]
    assert 'api.accountExport()' in export_body
    assert "obrasignal-account-export.json" in export_body
    assert 'Share.share' in export_body
    assert 'console.' not in export_body
