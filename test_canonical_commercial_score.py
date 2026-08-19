from opportunity_match_pipeline import evaluate_row


def _profile():
    return {
        "activity": "metalomecânica",
        "keywords": [],
        "exclude_keywords": [],
        "countries": [],
        "cpv_prefixes": [],
        "min_value": None,
        "max_value": None,
        "excluded_procedure_types": [],
        "hard_exclusions": [],
        "services": [],
        "capability_tags": [],
        "project_scales": [],
        "certifications": [],
    }


def _row(legacy_score):
    return {
        "source": "TEST",
        "external_id": "canonical-score",
        "title": "Construção de estrutura metálica para armazém",
        "description": "Empreitada de montagem e execução de estrutura metálica.",
        "buyer": "Entidade pública",
        "country": "PRT",
        "cpv": "45260000",
        "value": "200000 EUR",
        "value_numeric": 200000,
        "deadline": "2099-12-31",
        "procedure_type": "open",
        "locations": [{"country": "PRT"}],
        "score": legacy_score,
    }


def test_pipeline_uses_commercial_v2_instead_of_legacy_source_score():
    low_legacy = evaluate_row(_row(0), profile=_profile())
    high_legacy = evaluate_row(_row(100), profile=_profile())

    assert low_legacy["commercial"]["rule_version"] == "commercial-v2"
    assert low_legacy["profile_score"] == high_legacy["profile_score"]
    assert low_legacy["decision"] == high_legacy["decision"]
