from commercial_score_v2 import RULE_VERSION, score_v2


def test_structured_works_cpv_scores_strongly():
    result = score_v2({
        "title": "Construção de estrutura metálica",
        "description": "Empreitada de montagem de estrutura e cobertura",
        "cpv": "45223100-7",
        "deadline": "2099-12-31",
        "value_numeric": 180000,
        "procedure_type": "open procedure",
    })
    assert result["score"] >= 70
    assert result["components"]["cpv_fit"] == 35
    assert result["rule_version"] == RULE_VERSION


def test_expired_notice_cannot_get_deadline_points():
    result = score_v2({
        "title": "Construção de obra",
        "description": "empreitada",
        "cpv": "45000000-7",
        "deadline": "2000-01-01",
        "value_numeric": 100000,
        "procedure_type": "open procedure",
    })
    assert result["components"]["deadline"] == 0
    assert result["deadline_days"] < 0


def test_large_value_is_penalized_but_not_hidden():
    result = score_v2({
        "title": "Construção e montagem",
        "description": "estrutura metálica",
        "cpv": "45223100-7",
        "deadline": "2099-12-31",
        "value_numeric": 10_000_000,
        "procedure_type": "open procedure",
    })
    assert result["components"]["size_fit"] == 2
    assert result["score"] >= 40


def test_intellectual_only_work_is_penalized():
    result = score_v2({
        "title": "Serviços de arquitetura",
        "description": "consultoria e projeto de arquitetura",
        "cpv": "71200000-0",
        "deadline": "2099-12-31",
        "value_numeric": 100000,
        "procedure_type": "open procedure",
    })
    assert result["components"]["capability_fit"] == 0
    assert result["components"]["access"] <= 3
