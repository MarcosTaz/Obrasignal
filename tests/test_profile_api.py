import api


def test_profile_api_round_trip(monkeypatch, tmp_path):
    profile_path = tmp_path / "profile.json"
    monkeypatch.setenv("OBRASIGNAL_PROFILE", str(profile_path))

    client = api.APP.test_client()
    payload = {
        "name": "Empresa Demo",
        "activity": "estruturas metálicas",
        "regions": ["Leiria", "Coimbra"],
        "geographic_radius_km": 100,
        "services": ["fabrico e montagem"],
        "capability_tags": ["estruturas metálicas"],
        "project_scales": ["medium"],
        "certifications": ["ISO 9001"],
        "preferred_procedure_types": ["open"],
        "excluded_procedure_types": ["negotiated"],
        "hard_exclusions": ["consultoria"],
        "min_value": 100000,
        "max_value": 1000000,
    }

    response = client.post("/api/v1/profile", json=payload)
    assert response.status_code == 200
    stored = response.get_json()["profile"]
    assert stored["regions"] == ["Leiria", "Coimbra"]
    assert stored["geographic_radius_km"] == 100
    assert stored["services"] == ["fabrico e montagem"]
    assert stored["preferred_procedure_types"] == ["open"]
    assert stored["excluded_procedure_types"] == ["negotiated"]

    readback = client.get("/api/v1/profile")
    assert readback.status_code == 200
    assert readback.get_json()["profile"] == stored
