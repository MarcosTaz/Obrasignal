"""Explanation-faithfulness regressions for profile scoring."""

from opportunity_match_pipeline import evaluate_row
from profile_scoring import personalized_score


def _profile(**overrides):
    base = {
        "account_id": "explanation-test",
        "activity": "",
        "contract_interests": [],
        "keywords": [],
        "exclude_keywords": [],
        "countries": [],
        "cpv_prefixes": [],
        "min_value": None,
        "max_value": None,
        "economic_min_score": 0,
        "preferred_procedure_types": [],
        "excluded_procedure_types": [],
        "regions": [],
        "geographic_radius_km": None,
        "services": [],
        "capability_tags": [],
        "project_scales": [],
        "certifications": [],
        "hard_exclusions": [],
    }
    base.update(overrides)
    return base


def _profile_factor(result):
    return next(factor for factor in result["explanation"]["factors"] if factor["key"] == "profile")


def test_no_profile_signal_does_not_claim_profile_correspondence():
    row = {"title": "Contrato genérico", "description": "Sem sinais da empresa", "score": 40}

    score, _label, _cls, reason = personalized_score(row, base_score=40, profile=_profile())

    assert score == 40
    assert reason == "sem evidência adicional do perfil; preservado score comercial"
    assert "correspondência" not in reason.lower()


def test_pipeline_profile_factor_uses_actual_no_signal_reason():
    row = {
        "source": "TEST",
        "external_id": "no-profile-signal",
        "title": "Serviço genérico",
        "description": "Objeto sem correspondência de capacidade declarada",
        "deadline": "2099-01-01",
    }

    result = evaluate_row(row, _profile())
    factor = _profile_factor(result)

    assert factor["reason"] == "sem evidência adicional do perfil; preservado score comercial"
    assert factor["reason"] != "Compatibilidade com o perfil da empresa"


def test_pipeline_profile_factor_names_only_signals_that_actually_contributed():
    row = {
        "source": "TEST",
        "external_id": "profile-signals",
        "title": "Construção de pavilhão",
        "description": "Execução de construção de pavilhão industrial",
        "country": "PRT",
        "cpv": "45213220",
        "value": "250000",
        "value_numeric": 250000,
        "deadline": "2099-01-01",
        "procedure_type": "open procedure",
    }
    profile = _profile(
        countries=["PRT"],
        cpv_prefixes=["4521"],
        min_value=50_000,
        max_value=500_000,
        services=["construção de pavilhão industrial"],
        capability_tags=["construção de pavilhão"],
    )

    result = evaluate_row(row, profile)
    reason = _profile_factor(result)["reason"]

    assert "mercado preferido" in reason
    assert "CPV compatível" in reason
    assert "valor dentro do intervalo" in reason
    assert "penalizado:" not in reason


def test_profile_penalty_is_explained_when_exclusion_contributes():
    row = {
        "title": "Consultoria de projeto",
        "description": "Serviços de consultoria",
        "country": "PRT",
    }
    profile = _profile(exclude_keywords=["consultoria"])

    _score, _label, _cls, reason = personalized_score(row, base_score=50, profile=profile)

    assert "penalizado: consultoria" in reason
