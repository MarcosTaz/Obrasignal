from opportunity_match_pipeline import evaluate_row


def test_capability_exclusion_blocks_qualification():
    profile = {
        "countries": {"PRT"},
        "cities": {"LEIRIA"},
        "postal_prefixes": {"24"},
        "min_value": 100000,
        "max_value": 1000000,
        "cpv_prefixes": ["45"],
        "hard_exclusions": ["ponte"],
        "services": ["estruturas metálicas"],
        "capability_tags": ["construção"],
    }
    row = {
        "source": "TED",
        "external_id": "cap-1",
        "title": "Construção de ponte metálica",
        "description": "Empreitada de estruturas metálicas",
        "country": "PRT",
        "cpv": "45221100-3",
        "value_numeric": 300000,
        "deadline": "2099-12-31",
        "profile_score": 90,
        "locations": [{"country": "PRT", "city": "Leiria"}],
    }
    result = evaluate_row(row, profile)
    assert result["decision"] == "REJECT"
    assert any("ponte" in item for item in result["hard_capability_blockers"])
    assert result["profile_score"] <= 35


def test_capability_evidence_is_returned_for_matching_opportunity():
    profile = {
        "countries": {"PRT"},
        "cities": {"LEIRIA"},
        "postal_prefixes": {"24"},
        "min_value": 100000,
        "max_value": 1000000,
        "cpv_prefixes": ["45"],
        "services": ["estruturas metálicas"],
        "capability_tags": ["construção"],
    }
    row = {
        "source": "TED",
        "external_id": "cap-2",
        "title": "Construção de estrutura metálica",
        "description": "Empreitada de montagem de estruturas metálicas",
        "country": "PRT",
        "cpv": "45223100-7",
        "value_numeric": 300000,
        "deadline": "2099-12-31",
        "profile_score": 90,
        "locations": [{"country": "PRT", "city": "Leiria"}],
    }
    result = evaluate_row(row, profile)
    assert result["capability_evidence"]["matched"] is True
    assert result["hard_capability_blockers"] == []


def test_expired_opportunity_is_rejected_even_with_strong_fit():
    result = evaluate_row({
        "source": "TED", "external_id": "expired", "title": "Estrutura metálica",
        "description": "Empreitada de montagem", "country": "PRT", "cpv": "45223100-7",
        "value_numeric": 300000, "deadline": "2000-01-01",
    }, {"countries": ["PRT"], "cpv_prefixes": ["45"], "keywords": ["estrutura metálica"]})

    assert result["decision"] == "REJECT"
    assert "prazo de apresentação terminado" in result["hard_capability_blockers"]
    assert result["profile_score"] <= 35
