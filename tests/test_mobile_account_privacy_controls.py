from pathlib import Path
import re


API = Path('mobile/src/api.js').read_text(encoding='utf-8')
OWNER = Path('mobile/components/AccountPrivacyControls.js').read_text(encoding='utf-8')
BILLING = Path('mobile/components/BillingGate.js').read_text(encoding='utf-8')


def test_customer_client_exposes_authenticated_account_privacy_owner_routes():
    assert "accountExport:()=>readWhenReady('/account/export')" in API
    assert "accountDeletionStatus:()=>readWhenReady('/account/deletion')" in API
    assert re.search(r"requestAccountDeletion:\(confirmation\)=>writeWhenReady\('/account/deletion',\{method:'POST',body:JSON\.stringify\(\{confirmation\}\)\}\)", API)


def test_destructive_deletion_requires_exact_server_confirmation_literal():
    assert "const DELETE_CONFIRMATION = 'DELETE_MY_OBRASIGNAL_DATA'" in OWNER
    assert "confirmation !== DELETE_CONFIRMATION" in OWNER
    assert "body:JSON.stringify({confirmation})" in API
    assert "Pedir eliminação dos dados privados" in OWNER


def test_pending_deletion_copy_does_not_overclaim_external_revocation():
    assert "revogação externa" in OWNER
    assert "não é apresentada como totalmente eliminada" in OWNER
    assert "O ObraSignal não assume que os dados foram eliminados" in OWNER


def test_accepted_deletion_locks_private_ui_and_attempts_local_purge_and_signout():
    request_body = OWNER.split('const requestDeletion = async () => {', 1)[1].split('if (!lifecycleReady)', 1)[0]
    assert 'setPrivacyLocked(true)' in request_body
    assert 'await storage.bindPrivateTenant(null)' in request_body
    assert 'await supabase.auth.signOut()' in request_body
    assert 'A revogação externa continua pendente.' in request_body


def test_export_is_customer_initiated_without_console_logging_or_false_file_claim():
    export_body = OWNER.split('const prepareExport = async () => {', 1)[1].split('const requestDeletion', 1)[0]
    assert 'api.accountExport()' in export_body
    assert "schema_version !== 'account-export.v1'" in export_body
    assert 'console.' not in export_body
    assert 'Este build não afirma que criou um ficheiro no dispositivo.' in OWNER


def test_billing_gate_does_not_duplicate_privacy_lifecycle_owner():
    assert 'requestAccountDeletion' not in BILLING
    assert 'accountExport' not in BILLING
    assert 'DELETE_MY_OBRASIGNAL_DATA' not in BILLING
