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


def test_jwt_subject_is_private_and_binds_api_identity() -> None:
    text = _text()
    assert "open('/tmp/token_subject', 'w', encoding='utf-8').write(str(subject))" in text
    assert "token_subject=open('/tmp/token_subject', encoding='utf-8').read()" in text
    assert "assert str(account_id) == token_subject" in text
    assert 'cat /tmp/token_subject' not in text
    assert "print(subject" not in text
    assert "print('subject" not in text


def test_live_jwt_provider_diagnostics_are_fail_closed() -> None:
    text = _text()
    assert 'token_alg_allowed = alg in {"RS256", "ES256"}' in text
    assert 'token_kid_present = kid is not None and str(kid) in provider_kids' in text
    assert 'token_issuer_matches = issuer == os.environ["EXPECTED_ISSUER"]' in text
    assert 'token_audience_authenticated = "authenticated" in audiences' in text
    assert "assert token_alg_allowed, 'Supabase token algorithm is not supported'" in text
    assert "assert token_kid_present, 'Supabase token key id is not present in provider JWKS'" in text
    assert "assert token_issuer_matches, 'Supabase token issuer does not match project issuer'" in text
    assert "assert token_audience_authenticated, 'Supabase token audience is not authenticated'" in text
    assert "TOKEN_ALG_ALLOWED=" in text
    assert "TOKEN_KID_PRESENT_IN_PROVIDER_JWKS=" in text
    assert "TOKEN_ISSUER_MATCHES_SUPABASE_PROJECT=" in text
    assert "TOKEN_AUDIENCE_AUTHENTICATED=" in text


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


def test_conditional_journey_coverage_is_explicit() -> None:
    text = _text()
    assert "open('/tmp/authenticated_e2e_coverage','w').write('UNKNOWN_NO_DATA')" in text
    assert "open('/tmp/authenticated_e2e_coverage','w').write('PENDING')" in text
    assert "open('/tmp/authenticated_e2e_coverage','w').write('FULL')" in text
    assert 'coverage="$(cat /tmp/authenticated_e2e_coverage)"' in text
    assert 'FULL|UNKNOWN_NO_DATA)' in text
    assert 'echo "coverage=$coverage" >> "$GITHUB_OUTPUT"' in text
    assert 'echo "AUTHENTICATED_E2E_COVERAGE=$coverage" >> "$GITHUB_STEP_SUMMARY"' in text


def test_nested_endpoint_filename_guard_is_preserved() -> None:
    text = _text()
    assert "tr '/' '_'" in text
    assert 'Unsafe E2E output filename' in text
