import json

from company_profile import DEFAULT_PROFILE, normalize_profile


def test_normalize_profile_supports_configurable_business_rules():
    profile = normalize_profile({
        "name": "Empresa X",
        "activity": "metalomecânica",
        "regions": "Leiria,Pombal",
        "geographic_radius_km": "80",
        "services": ["estruturas metálicas", "coberturas"],
        "capability_tags": ["serralharia"],
        "project_scales": ["medium", "large"],
        "certifications": ["ISO 9001"],
        "min_value": "100000",
        "max_value": 1000000,
        "economic_min_score": 65,
        "min_deadline_days": 10,
        "max_deadline_days": 90,
        "preferred_procedure_types": ["OPEN"],
        "excluded_procedure_types": ["NEGOTIATED"],
        "hard_exclusions": ["ponte"],
        "profile_coordinates": {"lat": 39.744, "lon": -8.807},
    })

    assert profile["regions"] == ["Leiria", "Pombal"]
    assert profile["geographic_radius_km"] == 80
    assert profile["services"] == ["estruturas metálicas", "coberturas"]
    assert profile["project_scales"] == ["medium", "large"]
    assert profile["economic_min_score"] == 65
    assert profile["profile_coordinates"] == {"lat": 39.744, "lon": -8.807}
    assert "metalomecânica" in profile["keywords"]


def test_invalid_numeric_ranges_are_rejected():
    try:
        normalize_profile({"min_value": 200, "max_value": 100})
    except ValueError as exc:
        assert "min_value" in str(exc)
    else:
        raise AssertionError("expected invalid value range to be rejected")


def test_default_profile_remains_backward_compatible():
    assert DEFAULT_PROFILE["countries"] == ["PRT"]
    assert "cpv_prefixes" in DEFAULT_PROFILE
    assert "economic_min_score" in DEFAULT_PROFILE
