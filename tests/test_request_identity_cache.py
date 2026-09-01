import os

from flask import Flask, request

import auth_context
from auth_context import RequestIdentity


def test_provider_mode_reuses_only_explicit_request_cached_identity(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setenv('OBRASIGNAL_AUTH_MODE', 'provider')
    expected = RequestIdentity(account_id='tenant-a', authenticated=True, subject='tenant-a', claims={'sub':'tenant-a'})

    class BombVerifier:
        def verify(self, _token):
            raise AssertionError('verifier should not be called when a verified request identity is cached')

    monkeypatch.setattr(auth_context, 'production_verifier', lambda: BombVerifier())
    with app.test_request_context('/api/v1/push/status', headers={'Authorization':'Bearer token'}):
        request.obrasignal_identity = expected
        assert auth_context.configured_identity() is expected


def test_provider_mode_validates_bearer_once_within_same_request(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setenv('OBRASIGNAL_AUTH_MODE', 'provider')
    calls = []

    class Verifier:
        def verify(self, token):
            calls.append(token)
            return type('Identity', (), {
                'account_id': 'tenant-once',
                'subject': 'tenant-once',
                'claims': {'sub': 'tenant-once'},
            })()

    verifier = Verifier()
    monkeypatch.setattr(auth_context, 'production_verifier', lambda: verifier)
    with app.test_request_context('/api/v1/stats', headers={'Authorization':'Bearer verified-token'}):
        first = auth_context.configured_identity()
        second = auth_context.configured_identity()
        assert first is second
        assert first.account_id == 'tenant-once'
        assert calls == ['verified-token']


def test_provider_mode_does_not_trust_arbitrary_non_identity_cache(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setenv('OBRASIGNAL_AUTH_MODE', 'provider')
    calls = []

    class Verifier:
        def verify(self, token):
            calls.append(token)
            return type('Identity', (), {'account_id':'tenant-b','subject':'tenant-b','claims':{'sub':'tenant-b'}})()

    monkeypatch.setattr(auth_context, 'production_verifier', lambda: Verifier())
    with app.test_request_context('/api/v1/push/status', headers={'Authorization':'Bearer verified-token'}):
        request.obrasignal_identity = {'account_id':'attacker'}
        identity = auth_context.configured_identity()
        assert identity.account_id == 'tenant-b'
        assert calls == ['verified-token']
