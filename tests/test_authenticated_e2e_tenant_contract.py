from pathlib import Path


WORKFLOW = Path('.github/workflows/authenticated-e2e.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_authenticated_identity_is_persisted_privately_and_not_logged() -> None:
    text = _text()
    assert "open('/tmp/authenticated_account_id', 'w', encoding='utf-8').write(str(account_id))" in text
    assert "Authenticated API identity verified for account:" not in text
    assert "print('Authenticated API identity verified.')" in text
    assert 'cat /tmp/authenticated_account_id' not in text


def test_profile_persistence_responses_bind_to_authenticated_identity() -> None:
    text = _text()
    assert "/tmp/profile-write-response.json" in text
    assert "/tmp/profile-restore-response.json" in text
    assert text.count("expected_account_id=open('/tmp/authenticated_account_id', encoding='utf-8').read()") >= 6
    assert "assert str(payload.get('account_id')) == expected_account_id" in text
    assert text.count("assert payload.get('authenticated') is True") >= 4


def test_account_scoped_responses_bind_to_authenticated_identity() -> None:
    text = _text()
    assert "assert str(payload.get('account_id')) == expected_account_id" in text
    assert "assert str(stats.get('account_id')) == expected_account_id" in text
    assert "assert str(workflow.get('account_id')) == expected_account_id" in text


def test_nested_endpoint_filename_guard_is_preserved() -> None:
    text = _text()
    assert "tr '/' '_'" in text
    assert 'Unsafe E2E output filename' in text
