from pathlib import Path

BILLING = Path('mobile/components/BillingGate.js')
AUTH = Path('mobile/components/AuthGate.js')


def test_account_privacy_has_single_outer_owner_outside_billing_gate():
    billing = BILLING.read_text(encoding='utf-8')
    auth = AUTH.read_text(encoding='utf-8')

    assert '<AccountPrivacyControls' in auth
    assert '<BillingGate' in auth
    assert 'AccountPrivacyControls key=' in auth
    assert 'requestAccountDeletion' not in billing
    assert 'accountExport' not in billing
    assert 'DELETE_MY_OBRASIGNAL_DATA' not in billing


def test_billing_gate_cannot_offer_deletion_without_outer_lifecycle_lock():
    billing = BILLING.read_text(encoding='utf-8')

    assert 'Eliminar conta e dados do produto' not in billing
    assert 'signOutAfterDeletion' not in billing
    assert 'deletionState' not in billing
