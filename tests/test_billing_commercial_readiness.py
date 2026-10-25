from app import APP
from account_registry import billing_provider_readiness


def test_billing_readiness_probe_is_boolean_only_and_fail_closed(monkeypatch):
    monkeypatch.delenv('REVENUECAT_SECRET_API_KEY', raising=False)
    monkeypatch.delenv('REVENUECAT_WEBHOOK_SECRET', raising=False)
    monkeypatch.delenv('OBRASIGNAL_LIVE_BILLING_APPROVED', raising=False)
    response = APP.test_client().get('/api/v1/billing/readiness')
    assert response.status_code == 200
    assert response.get_json() == {'commercial_ready': False}


def test_billing_readiness_probe_requires_both_backend_paths_and_operator_approval(monkeypatch):
    monkeypatch.setenv('REVENUECAT_SECRET_API_KEY', 'subscriber-secret')
    monkeypatch.delenv('REVENUECAT_WEBHOOK_SECRET', raising=False)
    monkeypatch.delenv('OBRASIGNAL_LIVE_BILLING_APPROVED', raising=False)
    assert billing_provider_readiness()['commercial_ready'] is False

    monkeypatch.setenv('REVENUECAT_WEBHOOK_SECRET', 'webhook-secret')
    response = APP.test_client().get('/api/v1/billing/readiness')
    assert response.status_code == 200
    assert response.get_json() == {'commercial_ready': False}

    monkeypatch.setenv('OBRASIGNAL_LIVE_BILLING_APPROVED', 'true')
    response = APP.test_client().get('/api/v1/billing/readiness')
    assert response.status_code == 200
    assert response.get_json() == {'commercial_ready': True}

    monkeypatch.delenv('REVENUECAT_SECRET_API_KEY')
    response = APP.test_client().get('/api/v1/billing/readiness')
    assert response.status_code == 200
    assert response.get_json() == {'commercial_ready': False}
