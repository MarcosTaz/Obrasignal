"""Change-impact composition probe for #466 explanation × #477 matching semantics.

DRAFT/TEST-ONLY composition evidence. This file does not define product wording;
it only requires the explanation to describe the scoring signals that actually
contributed after normalization semantics change.
"""

from opportunity_match_pipeline import evaluate_row
from profile_scoring import personalized_score


def _profile(**overrides):
    base = {
        "account_id": "composition-test",
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


def _row(title, **overrides):
    row = {
        "source": "TEST",
        "external_id": title,
        "title": title,
        "description": "",
        "buyer": "",
        "country": "",
        "cpv": "",
        "value": "",
        "value_numeric": None,
        "deadline": "2099-01-01",
        "procedure_type": "",
    }
    row.update(overrides)
    return row


def _profile_reason(result):
    return next(
        factor["reason"]
        for factor in result["explanation"]["factors"]
        if factor["key"] == "profile"
    )


def test_normalization_false_negative_repair_is_explained_by_actual_profile_term():
    profile = _profile(keywords=["climatização"])
    row = _row("Instalacao de sistema de climatizacao")

    score, _label, _cls, scorer_reason = personalized_score(row, base_score=40, profile=profile)
    result = evaluate_row(row, profile)

    assert score == 46
    assert scorer_reason == "perfil: climatização"
    assert "perfil: climatização" in _profile_reason(result)


def test_boundary_hard_negative_does_not_leave_stale_positive_profile_reason():
    profile = _profile(keywords=["obras"])
    row = _row("Gestão de sobras de materiais")

    score, _label, _cls, scorer_reason = personalized_score(row, base_score=40, profile=profile)
    result = evaluate_row(row, profile)
    explanation_reason = _profile_reason(result)

    assert score == 40
    assert scorer_reason == "sem evidência adicional do perfil; preservado score comercial"
    assert explanation_reason == scorer_reason
    assert "perfil: obras" not in explanation_reason


def test_normalized_exclusion_remains_visible_as_negative_reason():
    profile = _profile(exclude_keywords=["fiscalização"])
    row = _row("Servicos de fiscalizacao")

    score, _label, _cls, scorer_reason = personalized_score(row, base_score=40, profile=profile)
    result = evaluate_row(row, profile)

    assert score == 28
    assert "penalizado: fiscalização" in scorer_reason
    assert "penalizado: fiscalização" in _profile_reason(result)


def test_punctuation_variant_keeps_real_match_reason():
    profile = _profile(keywords=["avac"])
    row = _row("Instalação AVAC, edifício municipal")

    _score, _label, _cls, scorer_reason = personalized_score(row, base_score=40, profile=profile)
    result = evaluate_row(row, profile)

    assert scorer_reason == "perfil: avac"
    assert "perfil: avac" in _profile_reason(result)


def test_multiple_contributing_signals_are_not_reduced_to_stale_single_reason():
    profile = _profile(
        keywords=["obras"],
        countries=["PRT"],
        cpv_prefixes=["4521"],
        min_value=50_000,
        max_value=500_000,
    )
    row = _row(
        "Execução de obras municipais",
        country="PRT",
        cpv="45213220",
        value="250000",
        value_numeric=250_000,
    )

    _score, _label, _cls, scorer_reason = personalized_score(row, base_score=40, profile=profile)
    result = evaluate_row(row, profile)
    explanation_reason = _profile_reason(result)

    for expected in ("perfil: obras", "mercado preferido", "CPV compatível", "valor dentro do intervalo"):
        assert expected in scorer_reason
        assert expected in explanation_reason
