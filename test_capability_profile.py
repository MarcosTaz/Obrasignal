from capability_profile import build_capability_profile, capability_matches_text


def test_build_capability_profile_maps_existing_profile_fields():
    result = build_capability_profile({
        "name": "Empresa X",
        "activity": "construção e reabilitação",
        "countries": ["PRT"],
        "regions": ["Leiria", "Pombal"],
        "service_types": ["reabilitação"],
        "capability_tags": ["construcao"],
        "cpv_prefixes": ["45"],
        "min_value": 100000,
        "max_value": 1000000,
        "excluded_procedure_types": ["AJUSTE_DIRETO"],
    })

    assert result["name"] == "Empresa X"
    assert result["regions"] == ["Leiria", "Pombal"]
    assert result["services"] == ["reabilitação"]
    assert result["capability_tags"] == ["construcao"]
    assert result["min_value"] == 100000
    assert result["max_value"] == 1000000
    assert result["excluded_procedure_types"] == ["AJUSTE_DIRETO"]


def test_capability_profile_preserves_geographic_reference_points():
    result = build_capability_profile({
        "profile_coordinates": [{"latitude": 39.748, "longitude": -8.807, "label": "sede"}],
        "geographic_radius_km": 50,
    })
    assert result["geographic_radius_km"] == 50
    assert result["profile_coordinates"][0]["label"] == "sede"
    assert result["profile_coordinates"][0]["latitude"] == 39.748


def test_capability_match_returns_explainable_evidence():
    profile = build_capability_profile({
        "services": ["reabilitação", "coberturas"],
        "capability_tags": ["estruturas metálicas"],
    })

    result = capability_matches_text(
        profile,
        "Empreitada de reabilitação de cobertura e substituição de elementos.",
    )

    assert result["matched"] is True
    assert "reabilitação" in result["matched_services"]
    assert "coberturas" in result["matched_services"]
    assert result["evidence_count"] == 2


def test_capability_match_does_not_invent_evidence():
    profile = build_capability_profile({
        "services": ["pontes"],
        "capability_tags": ["engenharia naval"],
    })

    result = capability_matches_text(profile, "Reabilitação de escola municipal.")

    assert result["matched"] is False
    assert result["evidence_count"] == 0
