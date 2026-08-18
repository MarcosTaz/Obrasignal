from company_profile import derive_profile, load_profile, save_profile


def test_profile_includes_capability_fields(tmp_path, monkeypatch):
    path = tmp_path / "profile.json"
    monkeypatch.setenv("OBRASIGNAL_PROFILE", str(path))
    saved = save_profile({
        "activity": "estruturas metálicas",
        "regions": ["Leiria"],
        "geographic_radius_km": 120,
        "services": ["fabrico e montagem"],
        "capability_tags": ["steel structures"],
        "project_scales": ["medium"],
        "certifications": ["ISO 9001"],
        "hard_exclusions": ["consultoria"],
    })

    loaded = load_profile()
    assert saved["regions"] == ["Leiria"]
    assert loaded["geographic_radius_km"] == 120
    assert loaded["services"] == ["fabrico e montagem"]
    assert loaded["capability_tags"] == ["steel structures"]
    assert loaded["project_scales"] == ["medium"]
    assert loaded["certifications"] == ["ISO 9001"]
    assert loaded["hard_exclusions"] == ["consultoria"]
    assert "45" in loaded["cpv_prefixes"]
