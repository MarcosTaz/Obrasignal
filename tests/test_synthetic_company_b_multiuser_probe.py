from types import SimpleNamespace

import pytest
from flask import Flask

import auth_context


APP = Flask(__name__)


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


def test_two_signed_users_can_resolve_to_one_shared_company_with_distinct_roles(monkeypatch):
    with APP.test_request_context(headers={'Authorization': 'Bearer synthetic'}):
        _provider(monkeypatch, subject='user-owner', app_metadata={
            'obrasignal_account_id': 'company-b',
            'obrasignal_role': 'owner',
        })
        owner = auth_context.configured_identity()
        assert owner.account_id == 'company-b'
        assert owner.subject == 'user-owner'
        assert owner.role == 'owner'

    with APP.test_request_context(headers={'Authorization': 'Bearer synthetic'}):
        _provider(monkeypatch, subject='user-viewer', app_metadata={
            'obrasignal_account_id': 'company-b',
            'obrasignal_role': 'viewer',
        })
        viewer = auth_context.configured_identity()
        assert viewer.account_id == 'company-b'
        assert viewer.subject == 'user-viewer'
        assert viewer.role == 'viewer'


def test_shared_company_claims_fail_closed_when_partial_or_invalid(monkeypatch):
    invalid = [
        {'obrasignal_account_id': 'company-b'},
        {'obrasignal_role': 'editor'},
        {'obrasignal_account_id': '../company-b', 'obrasignal_role': 'owner'},
        {'obrasignal_account_id': 'company-b', 'obrasignal_role': 'admin'},
    ]
    for metadata in invalid:
        with APP.test_request_context(headers={'Authorization': 'Bearer synthetic'}):
            _provider(monkeypatch, subject='user-bad', app_metadata=metadata)
            with pytest.raises(Exception):
                auth_context.configured_identity()


def test_viewer_cannot_mutate_but_editor_and_owner_can(monkeypatch):
    assert auth_context.customer_role_allows('owner', 'POST') is True
    assert auth_context.customer_role_allows('editor', 'POST') is True
    assert auth_context.customer_role_allows('viewer', 'GET') is True
    assert auth_context.customer_role_allows('viewer', 'POST') is False
    assert auth_context.customer_role_allows('viewer', 'PATCH') is False
    assert auth_context.customer_role_allows('viewer', 'DELETE') is False


def test_account_deletion_requires_owner_even_when_editor_can_edit_workflow(monkeypatch):
    assert auth_context.customer_role_allows('editor', 'POST', owner_only=True) is False
    assert auth_context.customer_role_allows('owner', 'POST', owner_only=True) is True
