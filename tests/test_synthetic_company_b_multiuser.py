from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from jwt import InvalidTokenError

import auth_context


APP = Flask(__name__)
CORS_APP = Path('cors_app.py').read_text(encoding='utf-8')


def _provider(monkeypatch, *, subject, app_metadata):
    monkeypatch.setenv('OBRASIGNAL_AUTH_MODE', 'provider')
    monkeypatch.setattr(
        auth_context,
        'production_verifier',
        lambda: SimpleNamespace(
            verify=lambda _token: SimpleNamespace(
                account_id=subject,
                subject=subject,
                claims={'sub': subject, 'app_metadata': app_metadata},
            )
        ),
    )


def test_two_signed_users_resolve_to_one_shared_company_with_distinct_roles(monkeypatch):
    with APP.test_request_context(headers={'Authorization': 'Bearer synthetic'}):
        _provider(monkeypatch, subject='user-owner', app_metadata={
            'obrasignal_account_id': 'company-b',
            'obrasignal_role': 'owner',
        })
        owner = auth_context.configured_identity()
        assert (owner.account_id, owner.subject, owner.role) == ('company-b', 'user-owner', 'owner')

    with APP.test_request_context(headers={'Authorization': 'Bearer synthetic'}):
        _provider(monkeypatch, subject='user-viewer', app_metadata={
            'obrasignal_account_id': 'company-b',
            'obrasignal_role': 'viewer',
        })
        viewer = auth_context.configured_identity()
        assert (viewer.account_id, viewer.subject, viewer.role) == ('company-b', 'user-viewer', 'viewer')


def test_legacy_single_user_provider_identity_stays_owner_of_subject_account(monkeypatch):
    with APP.test_request_context(headers={'Authorization': 'Bearer synthetic'}):
        _provider(monkeypatch, subject='single-user-a', app_metadata={})
        identity = auth_context.configured_identity()
        assert identity.account_id == 'single-user-a'
        assert identity.role == 'owner'


def test_shared_company_claims_fail_closed_when_partial_or_invalid(monkeypatch):
    invalid = [
        {'obrasignal_account_id': 'company-b'},
        {'obrasignal_role': 'editor'},
        {'obrasignal_account_id': '../company-b', 'obrasignal_role': 'owner'},
        {'obrasignal_account_id': 'company-b', 'obrasignal_role': 'admin'},
        'not-a-dict',
    ]
    for metadata in invalid:
        with APP.test_request_context(headers={'Authorization': 'Bearer synthetic'}):
            _provider(monkeypatch, subject='user-bad', app_metadata=metadata)
            with pytest.raises(InvalidTokenError):
                auth_context.configured_identity()


def test_viewer_is_read_only_editor_can_write_owner_controls_destructive_boundary():
    assert auth_context.customer_role_allows('owner', 'POST') is True
    assert auth_context.customer_role_allows('editor', 'POST') is True
    assert auth_context.customer_role_allows('viewer', 'GET') is True
    assert auth_context.customer_role_allows('viewer', 'POST') is False
    assert auth_context.customer_role_allows('viewer', 'PATCH') is False
    assert auth_context.customer_role_allows('viewer', 'DELETE') is False
    assert auth_context.customer_role_allows('editor', 'POST', owner_only=True) is False
    assert auth_context.customer_role_allows('owner', 'POST', owner_only=True) is True
    assert auth_context.customer_role_allows('unknown', 'GET') is False


def test_production_wsgi_enforces_customer_mutation_roles_and_owner_only_deletion():
    assert 'from auth_context import configured_identity, customer_role_allows, InvalidTokenError' in CORS_APP
    assert 'def _authorize_customer_mutation()' in CORS_APP
    assert 'request.method not in {"POST", "PATCH", "DELETE"}' in CORS_APP
    assert 'request.path == "/api/v1/billing/webhook"' in CORS_APP
    assert 'owner_only = request.path == "/api/v1/account/deletion"' in CORS_APP
    assert 'customer_role_allows(identity.role, request.method, owner_only=owner_only)' in CORS_APP
    assert '"error": "authorization_denied"' in CORS_APP
