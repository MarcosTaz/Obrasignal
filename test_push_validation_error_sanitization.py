import sqlite3

from app import APP
import notification_events


def test_push_device_route_never_exposes_validation_exception_detail(monkeypatch):
    sentinel = "private-stack-path:/srv/tenant-a/provider-secret"

    def raise_private_error(*_args, **_kwargs):
        raise ValueError(sentinel)

    monkeypatch.setattr(notification_events, "register_push_device", raise_private_error)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-a")
    APP.config["OBRASIGNAL_DB_CONNECT"] = lambda: sqlite3.connect(":memory:")
    try:
        response = APP.test_client().post(
            "/api/v1/push/devices",
            json={
                "installation_id": "install-codeql-001",
                "expo_push_token": "ExpoPushToken[codeql]",
                "platform": "android",
            },
        )
        assert response.status_code == 400
        assert response.get_json() == {"error": "invalid_push_device_request"}
        assert sentinel not in response.get_data(as_text=True)
    finally:
        APP.config.pop("OBRASIGNAL_DB_CONNECT", None)
