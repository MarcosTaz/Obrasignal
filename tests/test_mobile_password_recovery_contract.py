from pathlib import Path


def test_auth_screen_exposes_reset_request_without_revealing_account_existence():
    source = Path("mobile/components/AuthScreen.tsx").read_text(encoding="utf-8")

    assert "resetPasswordForEmail" in source
    assert "Esqueci-me da palavra-passe" in source
    assert "Se existir uma conta com este email" in source
    assert "authRedirectTo()" in source


def test_session_coordinator_preserves_password_recovery_event_until_acknowledged():
    source = Path("mobile/src/sessionCoordinator.js").read_text(encoding="utf-8")

    assert "onAuthStateChange((event, session)" in source
    assert "publish(session, event || null)" in source
    assert "acknowledgeEvent()" in source
    assert "publish(state.session, null)" in source


def test_auth_gate_routes_recovery_before_normal_billing_shell_and_skips_warmup():
    source = Path("mobile/components/AuthGate.js").read_text(encoding="utf-8")

    assert "nextState.event !== 'PASSWORD_RECOVERY'" in source
    assert "authState.event === 'PASSWORD_RECOVERY'" in source
    assert "<PasswordRecoveryScreen />" in source
    assert source.index("authState.event === 'PASSWORD_RECOVERY'") < source.index("<BillingGate")


def test_recovery_screen_requires_confirmation_and_updates_supabase_user():
    source = Path("mobile/components/PasswordRecoveryScreen.tsx").read_text(encoding="utf-8")

    assert "password !== confirmPassword" in source
    assert "supabase.auth.updateUser({ password })" in source
    assert "authSession.acknowledgeEvent()" in source
    assert "Atualizar palavra-passe" in source
