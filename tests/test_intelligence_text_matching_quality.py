"""Metamorphic and hard-negative guards for profile text matching."""

from profile_scoring import personalized_score


def _profile(keywords=None, exclude_keywords=None):
    return {
        "activity": "",
        "keywords": keywords or [],
        "exclude_keywords": exclude_keywords or [],
        "countries": [],
        "cpv_prefixes": [],
        "min_value": None,
        "max_value": None,
    }


def _score(title, profile, base=40):
    return personalized_score(
        {"title": title, "description": "", "buyer": "", "score": base},
        base_score=base,
        profile=profile,
    )


def test_accented_and_ascii_portuguese_are_score_equivalent():
    profile = _profile(keywords=["climatização"])

    accented = _score("Instalação de sistema de climatização", profile)
    ascii_only = _score("Instalacao de sistema de climatizacao", profile)

    assert accented[0] == ascii_only[0] == 46
    assert "climatização" in accented[3]
    assert "climatização" in ascii_only[3]


def test_case_and_whitespace_do_not_change_phrase_match():
    profile = _profile(keywords=["instalações elétricas"])

    normal = _score("Instalações elétricas em edifício municipal", profile)
    variant = _score("INSTALACOES   ELETRICAS em edifício municipal", profile)

    assert normal[0] == variant[0] == 46


def test_keyword_does_not_match_inside_unrelated_larger_word():
    profile = _profile(keywords=["obras"])

    hard_negative = _score("Gestão de sobras de materiais", profile)
    clear_positive = _score("Execução de obras de reabilitação", profile)

    assert hard_negative[0] == 40
    assert "perfil:" not in hard_negative[3]
    assert clear_positive[0] == 46
    assert "perfil: obras" in clear_positive[3]


def test_exclusion_is_accent_insensitive_but_boundary_safe():
    profile = _profile(exclude_keywords=["fiscalização"])

    accented = _score("Serviços de fiscalização", profile)
    ascii_only = _score("Servicos de fiscalizacao", profile)
    larger_word = _score("Serviço fiscalizacaox experimental", profile)

    assert accented[0] == ascii_only[0] == 28
    assert "penalizado: fiscalização" in accented[3]
    assert "penalizado: fiscalização" in ascii_only[3]
    assert larger_word[0] == 40


def test_irrelevant_punctuation_and_json_field_order_do_not_change_score():
    profile = _profile(keywords=["avac"])
    first = {
        "title": "Instalação AVAC — edifício municipal",
        "description": "",
        "buyer": "",
        "score": 40,
    }
    second = {
        "buyer": "",
        "score": 40,
        "description": "",
        "title": "Instalação AVAC, edifício municipal",
    }

    assert personalized_score(first, base_score=40, profile=profile)[0] == 46
    assert personalized_score(second, base_score=40, profile=profile)[0] == 46
