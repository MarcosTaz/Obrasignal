from economic_fit import evaluate_economic_fit


def test_missing_value_is_unknown():
    result = evaluate_economic_fit(None, {})
    assert result["status"] == "UNKNOWN"
    assert result["score"] == 0
    assert result["confidence"] == 0


def test_without_company_rules_does_not_claim_profit():
    result = evaluate_economic_fit(150000, {})
    assert result["status"] == "REVIEW"
    assert result["score"] == 60
    assert result["confidence"] == 25
    assert "estimated_gross_profit" not in result
    assert "estimated_margin" not in result


def test_company_value_band_is_favourable():
    result = evaluate_economic_fit(150000, {"min_value": 100000, "max_value": 300000})
    assert result["status"] == "FAVOURABLE"
    assert result["score"] == 100
    assert result["confidence"] == 80


def test_below_company_minimum_is_unfavourable():
    result = evaluate_economic_fit(50000, {"min_value": 100000})
    assert result["status"] == "UNFAVOURABLE"
    assert result["score"] == 30


def test_above_company_maximum_is_unfavourable():
    result = evaluate_economic_fit(500000, {"max_value": 300000})
    assert result["status"] == "UNFAVOURABLE"
    assert result["score"] == 40


def test_deadline_window_is_explainable():
    result = evaluate_economic_fit(
        150000,
        {"min_deadline_days": 10, "max_deadline_days": 30},
        {"deadline": "2026-09-07"},
        today=__import__("datetime").date(2026, 8, 18),
    )
    assert result["status"] == "FAVOURABLE"
    assert result["score"] == 80
    assert all(rule["passed"] for rule in result["rules"])


def test_excluded_procedure_is_unfavourable():
    result = evaluate_economic_fit(
        150000,
        {"excluded_procedure_types": ["OPEN"]},
        {"procedure_type": "OPEN"},
    )
    assert result["status"] == "UNFAVOURABLE"
    assert result["score"] == 20
    assert result["rules"][-1]["passed"] is False
