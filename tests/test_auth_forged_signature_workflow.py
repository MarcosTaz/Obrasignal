from pathlib import Path


WORKFLOW = Path('.github/workflows/auth-forged-signature-e2e.yml')
AUTH_CRITICAL_WITH_CHECKOUT = (
    Path('.github/workflows/authenticated-e2e.yml'),
    Path('.github/workflows/auth-forged-signature-e2e.yml'),
    Path('.github/workflows/auth-verifier-live.yml'),
)
CHECKOUT_SHA = '11d5960a326750d5838078e36cf38b85af677262'


def test_forged_signature_boundary_preserves_header_and_claims() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert "header, payload, signature = token.split('.')" in text
    assert "raw[0] ^= 1" in text
    assert "forged='.'.join((header, payload, forged_signature))" in text


def test_valid_token_acceptance_is_required_before_forgery_probe() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    baseline = text.index('Require real token acceptance baseline')
    rejection = text.index('Require forged signature rejection')
    assert baseline < rejection
    assert 'test "$status" = "200"' in text[baseline:rejection]
    assert "assert payload.get('authenticated') is True" in text[baseline:rejection]
    assert "assert payload.get('account_id')" in text[baseline:rejection]


def test_forged_token_remains_private_and_must_be_rejected() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert "open('/tmp/forged_token', 'w', encoding='utf-8').write(forged)" in text
    assert "print(forged" not in text
    assert 'authentication_required' in text
    assert 'test "$status" = "401"' in text


def test_boundary_waits_for_exact_production_sha() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert "assert health.get('build') == os.environ['TARGET_BUILD']" in text


def test_auth_critical_workflows_pin_checkout_and_drop_credentials() -> None:
    for workflow in AUTH_CRITICAL_WITH_CHECKOUT:
        text = workflow.read_text(encoding='utf-8')
        assert f'actions/checkout@{CHECKOUT_SHA} # v4' in text
        assert 'actions/checkout@v4' not in text
        assert 'persist-credentials: false' in text
        assert 'persist-credentials: true' not in text
        assert 'permissions:\n  contents: read' in text
