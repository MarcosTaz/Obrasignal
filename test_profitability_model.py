from profitability_model import estimate_profitability


def test_missing_value_is_unknown():
    result = estimate_profitability(None, {})
    assert result["status"] == "UNKNOWN"
    assert result["estimated_gross_profit"] is None
    assert result["confidence"] == 0


def test_default_estimate_is_conservative_and_not_net_profit():
    result = estimate_profitability(100000, {})
    assert result["status"] == "ATTRACTIVE"
    assert result["estimated_revenue"] == 100000
    assert result["estimated_cost"] == 85000
    assert result["estimated_gross_profit"] == 15000
    assert result["estimated_margin"] == 0.15
    assert result["confidence"] == 45


def test_explicit_cost_assumptions_raise_confidence():
    result = estimate_profitability(
        200000,
        {"target_margin": 0.20, "delivery_cost_ratio": 0.65, "risk_buffer": 0.05},
    )
    assert result["estimated_gross_profit"] == 60000
    assert result["estimated_margin"] == 0.30
    assert result["confidence"] == 90


def test_thin_margin_is_flagged():
    result = estimate_profitability(
        100000,
        {"target_margin": 0.25, "delivery_cost_ratio": 0.82, "risk_buffer": 0.08},
    )
    assert result["status"] == "THIN"
    assert result["estimated_gross_profit"] == 10000
