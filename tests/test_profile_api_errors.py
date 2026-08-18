import json

import api


def test_invalid_profile_returns_400_and_preserves_previous_profile(monkeypatch, tmp_path):
    profile_path = tmp_path / "profile.json"
    monkeypatch.setenv("OBRASIGNAL_PROFILE", str(profile_path))
    client = api.APP.test_client()

    valid = client.post(
        "/api/v1/profile",
        json={"name": "Empresa", "activity": "estruturas metálicas", "countries": ["PT"]},
    )
    assert valid.status_code == 200
    before = valid.get_json()["profile"]

    invalid = client.post(
        "/api/v1/profile",
        json={"min_value": 1000000, "max_value": 100000},
    )
    assert invalid.status_code == 400
    body = invalid.get_json()
    assert body["error"] == "INVALID_COMPANY_PROFILE"
    assert body["errors"]

    after = client.get("/api/v1/profile").get_json()["profile"]
    assert after == before
    assert json.loads(profile_path.read_text(encoding="utf-8")) == before


def test_invalid_profile_json_returns_400():
    client = api.APP.test_client()
    response = client.post(
        "/api/v1/profile",
        data="not-json",
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_json"


def test_invalid_query_parameters_return_400():
    client = api.APP.test_client()
    for url in ("/api/v1/alerts?limit=nope", "/api/v1/opportunities?minscore=nope", "/api/v1/opportunities?limit=nope"):
        response = client.get(url)
        assert response.status_code == 400
        assert response.get_json()["error"] == "invalid_parameter"
