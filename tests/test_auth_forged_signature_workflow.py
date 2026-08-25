from pathlib import Path


WORKFLOW = Path('.github/workflows/auth-forged-signature-e2e.yml')


def test_forged_signature_boundary_preserves_header_and_claims() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert "header, payload, signature = token.split('.')" in text
    assert "raw[0] ^= 1" in text
    assert "forged='.'.join((header, payload, forged_signature))" in text


def test_forged_token_remains_private_and_must_be_rejected() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert "open('/tmp/forged_token', 'w', encoding='utf-8').write(forged)" in text
    assert "print(forged" not in text
    assert 'authentication_required' in text
    assert 'test "$status" = "401"' in text


def test_boundary_waits_for_exact_production_sha() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert "assert health.get('build') == os.environ['TARGET_BUILD']" in text
