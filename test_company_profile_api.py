import json

import pytest

import api
from company_profile import DEFAULT_PROFILE, normalize_profile


def test_normalize_profile_preserves_all_configurable_fields():
    profile = normalize_profile({
        "name": "Empresa X",
        "activity": "metalomecânica",
        "regions": ["Leiria", "Pombal"],
        "geographic_radius_km": "80",
        "services": "estruturas metálicas, coberturas",
        "capability_tags": ["serralharia"],
        "project_scales": ["medium", "large"],
        "certifications": ["ISO 9001"],
        "min_value": "100000",
        "max_value": 1000000,
        "economic_min_score": "65",
        "min_deadline_days": 10,
        "max_deadline_days": 90,
        "preferred_procedure_types": ["OPEN"],
        "excluded_procedure_types": ["NEGOTIATED"],
        "hard_exclusions": ["ponte"],
    })

    assert profile["regions"] == ["Leiria", "Pombal"]
    assert profile["geographic_radius_km"] == 80
    assert profile["services"] == ["estruturas metálicas", "coberturas"]
    assert profile["project_scales"] == ["medium", "large"]
    assert profile["min_value"] == 100000
    assert profile["economic_min_score"] == 65
    assert profile["hard_exclusions"] == ["ponte"]


def test_normalize_profile_rejects_inverted_ranges():
    with pytest.raises(ValueError, match="min_value"):
        normalize_profile({"min_value": 500000, "max_value": 100000})

    with pytest.raises(ValueError, match="min_deadline_days"):
        normalize_profile({"min_deadline_days": 90, "max_deadline_days": 10})


def test_profile_post_accepts_full_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("OBRASIGNAL_PROFILE_FILE", str(tmp_path / "company_profile.json"))
    client = api.APP.test_client()

    response = client.post(
        "/api/v1/profile",
        json={
            "name": "Empresa X",
            "activity": "metalomecânica",
            "regions": ["Leiria"],
            "geographic_radius_km": 100,
            "services": ["estruturas metálicas"],
            "capability_tags": ["aço"],
            "project_scales": ["large"],
            "certifications": ["ISO 9001"],
            "min_value": 100000,
            "max_value": 2000000,
            "economic_min_score": 70,
            "min_deadline_days": 15,
            "max_deadline_days": 120,
            "preferred_procedure_types": ["OPEN"],
            "excluded_procedure_types": ["NEGOTIATED"],
            "hard_exclusions": ["ponte"],
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["profile"]["geographic_radius_km"] == 100
    assert payload["profile"]["hard_exclusions"] == ["ponte"]

    saved = json.loads((tmp_path / "company_profile.json").read_text(encoding="utf-8"))
    assert saved["economic_min_score"] == 70
    assert saved["preferred_procedure_types"] == ["OPEN"]


def test_profile_post_rejects_invalid_configuration(monkeypatch):
    client = api.APP.test_client()
    response = client.post(
        "/api/v1/profile",
        json={"min_value": 500000, "max_value": 100000},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "invalid_profile"
