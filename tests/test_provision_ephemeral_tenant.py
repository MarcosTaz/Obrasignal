from scripts import provision_ephemeral_tenant as pet


def test_admin_key_prefers_current_secret(monkeypatch):
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "current-secret")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "legacy-secret")
    monkeypatch.setenv("SUPABASE_ADMIN_KEY", "compat-secret")
    assert pet._admin_key() == "current-secret"


def test_admin_bootstrap_repairs_existing_confirmed_identity(monkeypatch):
    calls = []

    def fake_request(url, key, payload=None, method="POST"):
        calls.append((url, key, payload, method))
        if method == "GET":
            return 200, {"users": [{"id": "tenant-b-id", "email": pet.BOOTSTRAP_EMAIL}]}
        assert method == "PUT"
        assert url.endswith("/auth/v1/admin/users/tenant-b-id")
        assert payload["email_confirm"] is True
        assert payload["password"] == "derived-password"
        assert payload["user_metadata"]["purpose"] == pet.PURPOSE
        return 200, {}

    monkeypatch.setattr(pet, "_json_request", fake_request)
    pet._admin_bootstrap("https://example.supabase.co", "server-secret", "derived-password")
    assert [call[3] for call in calls] == ["GET", "PUT"]


def test_provider_session_uses_admin_bootstrap_without_email(monkeypatch):
    anonymous_calls = []
    admin_calls = []

    def fake_request(url, key, payload=None, method="POST"):
        anonymous_calls.append((url, key, payload, method))
        return 422, {"error_code": "anonymous_provider_disabled"}

    monkeypatch.setattr(pet, "_json_request", fake_request)
    monkeypatch.setattr(pet, "_derived_password", lambda: "derived-password")
    monkeypatch.setattr(pet, "_admin_key", lambda: "server-secret")
    monkeypatch.setattr(
        pet,
        "_admin_bootstrap",
        lambda base, key, password: admin_calls.append((base, key, password)),
    )
    monkeypatch.setattr(
        pet,
        "_password_signin",
        lambda base, key, password: (200, {}, ("masked-token", "tenant-b-id")),
    )

    session = pet._provider_session("https://example.supabase.co", "publishable-key")
    assert session == ("masked-token", "tenant-b-id")
    assert admin_calls == [
        ("https://example.supabase.co", "server-secret", "derived-password")
    ]
    assert len(anonymous_calls) == 1
