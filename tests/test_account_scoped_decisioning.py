from opportunity_match_pipeline import evaluate_row
from profile_scoring import personalized_score


def test_personalized_score_accepts_explicit_profiles():
    row = {
        "title": "Estrutura metálica para armazém",
        "description": "Execução de estrutura e montagem",
        "buyer": "Município",
        "country": "PRT",
        "cpv": "45000000",
        "value": "100000 EUR",
    }
    metal_profile = {
        "keywords": ["estrutura metálica"],
        "exclude_keywords": [],
        "countries": ["PRT"],
        "cpv_prefixes": ["45"],
        "min_value": None,
        "max_value": None,
    }
    other_profile = {
        "keywords": ["arquitetura"],
        "exclude_keywords": ["estrutura metálica"],
        "countries": ["ESP"],
        "cpv_prefixes": ["71"],
        "min_value": None,
        "max_value": None,
    }
    metal_score = personalized_score(row, base_score=40, profile=metal_profile)[0]
    other_score = personalized_score(row, base_score=40, profile=other_profile)[0]
    assert metal_score > other_score


def test_evaluate_row_uses_the_supplied_company_profile():
    row = {
        "source": "TEST",
        "external_id": "1",
        "title": "Estrutura metálica para armazém",
        "description": "Execução de estrutura e montagem",
        "buyer": "Município",
        "country": "PRT",
        "cpv": "45000000",
        "value": "100000 EUR",
        "value_numeric": 100000,
        "deadline": "2099-01-01",
        "score": 40,
    }
    profile = {
        "account_id": "company-a",
        "activity": "metalomecânica",
        "keywords": ["estrutura metálica"],
        "countries": ["PRT"],
        "cpv_prefixes": ["45"],
        "min_value": None,
        "max_value": None,
        "economic_min_score": 0,
        "preferred_procedure_types": [],
        "excluded_procedure_types": [],
        "exclude_keywords": [],
        "regions": [],
        "geographic_radius_km": None,
        "services": [],
        "capability_tags": ["metalomecânica"],
        "project_scales": [],
        "certifications": [],
        "hard_exclusions": [],
    }
    result = evaluate_row(row, profile=profile)
    assert result["profile_score"] > 40
