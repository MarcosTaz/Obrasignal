import os
import tempfile

import pytest


@pytest.fixture()
def profile_env(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "profile.json")
        monkeypatch.setenv("OBRASIGNAL_PROFILE", path)
        yield path


def test_profile_derivation(profile_env):
    from company_profile import derive_profile

    profile = derive_profile(
        "estruturas metálicas, pavilhões industriais e serralharia",
        {"countries": ["PT", "ES", "FR"], "min_value": 100000, "max_value": 2000000},
    )
    assert profile["activity"]
    assert any("metal" in x.lower() for x in profile["keywords"])
    assert profile["countries"] == ["PT", "ES", "FR"]


def test_strong_match_scores_high(profile_env):
    from company_profile import save_profile
    from profile_scoring import personalized_score

    save_profile({
        "activity": "estruturas metálicas, pavilhões industriais e serralharia",
        "keywords": ["estruturas metálicas", "pavilhões", "serralharia"],
        "countries": ["PT", "ES", "FR"],
        "cpv_prefixes": ["452", "454"],
        "min_value": 100000,
        "max_value": 2000000,
        "exclude_keywords": ["arquitetura", "fiscalização", "consultoria"],
    })
    row = {
        "score": 70,
        "title": "Construção de pavilhão industrial em estruturas metálicas",
        "description": "Fabrico e montagem de estruturas de aço e cobertura.",
        "buyer": "Município",
        "country": "ES",
        "cpv": "45213200",
        "value": "850000 EUR",
    }
    score, label, cls, reason = personalized_score(row)
    assert score >= 85
    assert label in ("ALERTA", "ALERTA MÁXIMO")
    assert "mercado preferido" in reason
    assert "CPV compatível" in reason


def test_excluded_service_is_penalized(profile_env):
    from company_profile import save_profile
    from profile_scoring import personalized_score

    save_profile({
        "activity": "estruturas metálicas",
        "keywords": ["estruturas metálicas"],
        "countries": ["PT", "ES", "FR"],
        "cpv_prefixes": ["452"],
        "min_value": 100000,
        "max_value": 2000000,
        "exclude_keywords": ["arquitetura", "fiscalização", "consultoria"],
    })
    row = {
        "score": 70,
        "title": "Serviços de arquitetura e fiscalização de obra",
        "description": "Projeto, arquitetura e fiscalização.",
        "buyer": "Município",
        "country": "ES",
        "cpv": "71200000",
        "value": "400000 EUR",
    }
    score, label, cls, reason = personalized_score(row)
    assert score < 70
    assert "penalizado" in reason


def test_non_preferred_country_loses_bonus(profile_env):
    from company_profile import save_profile
    from profile_scoring import personalized_score

    save_profile({
        "activity": "estruturas metálicas",
        "keywords": ["estruturas metálicas"],
        "countries": ["PT", "ES", "FR"],
        "cpv_prefixes": ["452"],
        "min_value": 100000,
        "max_value": 2000000,
        "exclude_keywords": [],
    })
    base = {
        "score": 70,
        "title": "Estruturas metálicas para pavilhão",
        "description": "Fabrico e montagem.",
        "buyer": "Public authority",
        "cpv": "45213200",
        "value": "850000 EUR",
    }
    preferred = personalized_score({**base, "country": "ES"})[0]
    other = personalized_score({**base, "country": "DE"})[0]
    assert preferred > other


def test_duplicate_identity_is_stable():
    from procurement_quality import opportunity_key

    a = {"source": "TED", "external_id": "ABC-123", "title": "Pavilhão"}
    b = {"source": "TED", "external_id": "ABC-123", "title": "Pavilhão atualizado"}
    assert opportunity_key(a) == opportunity_key(b)
