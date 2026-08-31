from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_privacy_controls_expose_current_backend_contract_without_false_completion_claims():
    surface = _text("mobile/components/AccountPrivacyControls.js")
    api = _text("mobile/src/api.js")

    assert "accountExport:()=>readWhenReady('/account/export')" in api
    assert "accountDeletionStatus:()=>readWhenReady('/account/deletion')" in api
    assert "requestAccountDeletion:(confirmation)=>writeWhenReady('/account/deletion'" in api

    assert "DELETE_MY_OBRASIGNAL_DATA" in surface
    assert "account-export.v1" in surface
    assert "CURRENT_CANONICAL_SERVER_ACCOUNT_DATA_ONLY" in surface
    assert "Este build não afirma que criou um ficheiro no dispositivo." in surface
    assert "PENDING — a conta não é apresentada como totalmente eliminada" in surface
    assert "confirmation !== DELETE_CONFIRMATION" in surface


def test_privacy_controls_wrap_billing_gate_so_rights_are_not_entitlement_gated():
    gate = _text("mobile/components/AuthGate.js")

    assert "import AccountPrivacyControls from './AccountPrivacyControls'" in gate
    privacy_open = gate.index("<AccountPrivacyControls")
    billing_open = gate.index("<BillingGate", privacy_open)
    billing_close = gate.index("</BillingGate>", billing_open)
    privacy_close = gate.index("</AccountPrivacyControls>", billing_close)
    assert privacy_open < billing_open < billing_close < privacy_close


def test_privacy_surface_keeps_destructive_action_explicit_and_fail_closed():
    surface = _text("mobile/components/AccountPrivacyControls.js")

    assert "if (deleteLoading || confirmation !== DELETE_CONFIRMATION) return" in surface
    assert "setDeleteError('Não foi possível concluir o pedido de eliminação." in surface
    assert "await refreshStatus()" in surface
    assert "deletionBlocked = status?.state === 'PENDING'" in surface
    assert "status?.state === 'UNKNOWN'" in surface
    assert "status?.state === 'NOT_FOUND'" in surface
