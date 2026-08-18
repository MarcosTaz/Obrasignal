import api


def test_profile_api_uses_request_identity_not_payload(monkeypatch, tmp_path):
    monkeypatch.setenv("OBRASIGNAL_PROFILE_DIR", str(tmp_path / "profiles"))
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-a")

    client = api.APP.test_client()
    response = client.post(
        "/api/v1/profile",
        json={
            "account_id": "account-b",
            "name": "Empresa A",
            "activity": "metalomecânica",
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["account_id"] == "account-a"
    assert body["profile"]["account_id"] == "account-a"


def test_profiles_are_selected_from_request_identity(monkeypatch, tmp_path):
    monkeypatch.setenv("OBRASIGNAL_PROFILE_DIR", str(tmp_path / "profiles"))
    client = api.APP.test_client()

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-a")
    assert client.post("/api/v1/profile", json={"name": "A"}).status_code == 200

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-b")
    assert client.post("/api/v1/profile", json={"name": "B"}).status_code == 200

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-a")
    a = client.get("/api/v1/profile").get_json()["profile"]
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-b")
    b = client.get("/api/v1/profile").get_json()["profile"]

    assert a["name"] == "A"
    assert b["name"] == "B"
