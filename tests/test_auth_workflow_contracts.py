from pathlib import Path


WORKFLOWS = Path(".github/workflows")


def test_manual_auth_diagnostic_does_not_expose_password_derivatives_or_hardcoded_accounts():
    workflow = (WORKFLOWS / "auth-diagnostic.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow
    assert "E2E_EMAIL: ${{ secrets.E2E_EMAIL }}" in workflow
    assert "password_sha256" not in workflow
    assert "password_byte_length" not in workflow
    assert "hashlib" not in workflow
    assert "@gmail.com" not in workflow
    assert "Authorization: Bearer $SUPABASE_KEY" not in workflow


def test_obsolete_duplicate_credentials_probe_is_removed():
    assert not (WORKFLOWS / "authenticated-e2e-app-credentials-probe.yml").exists()


def test_canonical_real_login_workflows_do_not_treat_publishable_key_as_bearer_token():
    authenticated = (WORKFLOWS / "authenticated-e2e.yml").read_text(encoding="utf-8")
    verifier_live = (WORKFLOWS / "auth-verifier-live.yml").read_text(encoding="utf-8")

    for workflow in (authenticated, verifier_live):
        assert '-H "apikey: $SUPABASE_KEY"' in workflow
        assert "Authorization: Bearer $SUPABASE_KEY" not in workflow


def test_authenticated_e2e_auth_failure_path_remains_silent_and_non_sensitive():
    workflow = (WORKFLOWS / "authenticated-e2e.yml").read_text(encoding="utf-8")

    # Provider login fails closed through curl --fail and never dumps the
    # provider body, password derivatives or derived credentials.
    assert 'curl --fail --silent --show-error --max-time 30' in workflow
    assert 'token=json.load(open(\'/tmp/auth.json\'' in workflow
    assert "API_AUTH_BODY=" not in workflow
    assert "API_AUTH_HEALTH=" not in workflow
    assert "OBRASIGNAL_JWT_ISSUER" not in workflow
    assert "OBRASIGNAL_JWKS_URL" not in workflow
    assert "print(exc" not in workflow
    assert "print(str(exc" not in workflow
    assert "repr(exc" not in workflow
    assert "traceback" not in workflow.lower()
    assert "password_sha256" not in workflow
    assert "password_byte_length" not in workflow


def test_authenticated_e2e_keeps_shared_profile_read_only():
    workflow = (WORKFLOWS / "authenticated-e2e.yml").read_text(encoding="utf-8")

    # Radar Production Readiness owns profile mutation/persistence proof. The
    # general authenticated E2E may read the shared probe profile but must never
    # mutate or restore it, otherwise concurrent gates can overwrite valid state.
    assert '"$API_URL/profile" > /tmp/profile.json' in workflow
    assert '-X POST "$API_URL/profile"' not in workflow
    assert "profile-restore" not in workflow
    assert "profile-write" not in workflow
    assert "__e2e_" not in workflow


def test_release_gates_and_manual_diagnostic_remain_separate():
    authenticated = (WORKFLOWS / "authenticated-e2e.yml").read_text(encoding="utf-8")
    smoke = (WORKFLOWS / "production-smoke.yml").read_text(encoding="utf-8")
    diagnostic = (WORKFLOWS / "auth-diagnostic.yml").read_text(encoding="utf-8")

    assert "branches: [main]" in authenticated
    assert "branches: [main]" in smoke
    assert "branches: [main]" not in diagnostic
    assert "API_URL: https://obrasignal.onrender.com/api/v1" in authenticated
    assert "https://obrasignal.onrender.com/api/v1/health" in smoke
