from pathlib import Path

SURFACE = Path('mobile/components/AccountPrivacyControls.js')


def test_destructive_request_locks_hydrated_private_shell_before_network_side_effect():
    source = SURFACE.read_text(encoding='utf-8')
    body = source.split('const requestDeletion = async () => {', 1)[1].split("const next = await api.requestAccountDeletion(confirmation)", 1)[0]

    # The request may commit server-side and lose its response. Private UI must be
    # hidden before the network side effect, then only reopened if a later status
    # refresh proves the account is still NONE.
    assert 'setPrivacyLocked(true)' in body


def test_ambiguous_delete_failure_relies_on_authoritative_refresh_before_reopen():
    source = SURFACE.read_text(encoding='utf-8')
    catch_body = source.split("setDeleteError('Não foi possível concluir o pedido de eliminação.", 1)[1].split('finally', 1)[0]
    assert 'await refreshStatus()' in catch_body
