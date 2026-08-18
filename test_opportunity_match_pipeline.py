from opportunity_match_pipeline import evaluate_row


def profile():
    return {
        "countries": {"PRT"},
        "nuts": set(),
        "cities": {"LEIRIA"},
        "postal_prefixes": {"24"},
    }


def test_evaluate_row_uses_lot_geography_profile_score_and_economics():
    row = {
        "source": "TED",
        "external_id": "123",
        "title": "Construção de estrutura metálica",
        "description": "empreitada de montagem",
        "country": "PRT",
        "cpv": "45223100-7",
        "value_numeric": 150000,
        "deadline": "2099-12-31",
        "profile_score": 82,
        "locations": [{"country": "PRT", "city": "Leiria"}],
    }
    result = evaluate_row(row, profile())
    assert result["lot_score"] >= 70
    assert result["geography"]["reason"] == "cidade prioritária"
    assert result["profitability"]["status"] == "ATTRACTIVE"
    assert result["profitability"]["estimated_gross_profit"] == 22500
    assert result["decision"] == "QUALIFIED"


def test_evaluate_row_does_not_qualify_weak_profile():
    row = {
        "source": "TED",
        "external_id": "124",
        "title": "Serviços de arquitetura",
        "description": "consultoria e projeto",
        "country": "PRT",
        "cpv": "71200000",
        "profile_score": 40,
        "locations": [{"country": "PRT", "city": "Leiria"}],
    }
    result = evaluate_row(row, profile())
    assert result["decision"] == "REJECT"
