import json

import pytest

import preload


@pytest.fixture
def client(tmp_path, monkeypatch):
    profile_path = tmp_path / "company_profile.json"
    monkeypatch.setenv("OBRASIGNAL_PROFILE_FILE", str(profile_path))
    preload.APP.config.update(TESTING=True)
    return preload.APP.test_client()


def test_profile_page_reads_saved_profile(client):
    response = client.get("/profile")
    assert response.status_code == 200
    assert "Perfil comercial" in response.get_data(as_text=True)
    assert "Critérios económicos" in response.get_data(as_text=True)


def test_profile_page_persists_complete_profile(client, tmp_path):
    response = client.post("/profile", data={
        "name": "Empresa X",
        "activity": "metalomecânica e coberturas",
        "countries": "PRT, ESP",
        "regions": "Leiria, Pombal",
        "geographic_radius_km": "80",
        "cpv_prefixes": "45, 44",
        "services": "estruturas metálicas, coberturas",
        "capability_tags": "serralharia, montagem",
        "project_scales": "medium, large",
        "certifications": "ISO 9001",
        "min_value": "100000",
        "max_value": "1000000",
        "economic_min_score": "65",
        "min_deadline_days": "10",
        "max_deadline_days": "90",
        "preferred_procedure_types": "OPEN",
        "excluded_procedure_types": "NEGOTIATED",
        "exclude_keywords": "arquitetura, fiscalização",
        "hard_exclusions": "ponte",
    })

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile?saved=1")

    saved = json.loads((tmp_path / "company_profile.json").read_text(encoding="utf-8"))
    assert saved["name"] == "Empresa X"
    assert saved["regions"] == ["Leiria", "Pombal"]
    assert saved["services"] == ["estruturas metálicas", "coberturas"]
    assert saved["min_value"] == 100000
    assert saved["economic_min_score"] == 65
    assert "metalomecânica" in saved["keywords"]


def test_profile_page_rejects_inverted_value_range(client):
    response = client.post("/profile", data={
        "min_value": "1000000",
        "max_value": "100000",
    })

    assert response.status_code == 400
    assert "min_value cannot exceed max_value" in response.get_data(as_text=True)
