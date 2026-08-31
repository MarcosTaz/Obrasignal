from pathlib import Path


APP = Path('mobile/App.js').read_text(encoding='utf-8')
COMPONENT = Path('mobile/components/AccountPrivacyControls.js')


def test_profile_exposes_customer_account_privacy_surface():
    assert COMPONENT.exists()
    assert 'AccountPrivacyControls' in APP
    assert '<AccountPrivacyControls' in APP


def test_privacy_surface_exposes_export_without_claiming_file_download():
    source = COMPONENT.read_text(encoding='utf-8')
    assert 'api.accountExport()' in source
    assert 'Exportar os meus dados' in source
    assert 'schema_version' in source
    assert 'CURRENT_CANONICAL_SERVER_ACCOUNT_DATA_ONLY' in source
    assert 'download' not in source.lower()


def test_deletion_surface_requires_exact_backend_confirmation_and_truthful_pending_state():
    source = COMPONENT.read_text(encoding='utf-8')
    assert 'DELETE_MY_OBRASIGNAL_DATA' in source
    assert 'api.accountDeletionStatus()' in source
    assert 'api.requestAccountDeletion(' in source
    assert 'PENDING' in source
    assert 'revogação externa' in source.lower() or 'revogacao externa' in source.lower()
    assert 'eliminada imediatamente' not in source.lower()


def test_privacy_surface_has_loading_error_and_destructive_confirmation_states():
    source = COMPONENT.read_text(encoding='utf-8')
    assert 'A carregar' in source
    assert 'Não foi possível' in source
    assert 'confirmation' in source
    assert 'TextInput' in source
