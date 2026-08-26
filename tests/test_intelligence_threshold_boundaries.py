from opportunity_match_pipeline import evaluate_row
from profile_scoring import personalized_score
from intelligence_counterfactual_audit import base_opportunity


def _neutral_profile():
    return {
        "activity": "",
        "contract_interests": [],
        "keywords": [],
        "exclude_keywords": [],
        "countries": [],
        "cpv_prefixes": [],
        "services": [],
        "capability_tags": [],
        "min_value": None,
        "max_value": None,
    }


def _label_at(score):
    row = {"title": "", "description": "", "buyer": "", "country": "", "cpv": "", "value": ""}
    return personalized_score(row, base_score=score, profile=_neutral_profile())[1]


def test_personalized_60_boundary_is_inclusive():
    assert _label_at(59) == "BAIXA PRIORIDADE"
    assert _label_at(60) == "NO RADAR"
    assert _label_at(61) == "NO RADAR"


def test_personalized_75_boundary_is_inclusive():
    assert _label_at(74) == "NO RADAR"
    assert _label_at(75) == "ALERTA"
    assert _label_at(76) == "ALERTA"


def test_personalized_90_boundary_is_inclusive():
    assert _label_at(89) == "ALERTA"
    assert _label_at(90) == "ALERTA MÁXIMO"
    assert _label_at(91) == "ALERTA MÁXIMO"


def test_no_positive_evidence_cap_stops_effective_profile_score_at_59():
    row = base_opportunity()
    profile = _neutral_profile()
    result = evaluate_row(row, profile=profile)

    assert result["profile_score"] <= 59
    assert result["capability_evidence"]["matched"] is False
    assert result["cpv_evidence"]["strength"] != "STRONG"


def test_lot_threshold_can_still_drive_review_when_profile_score_is_capped_below_60():
    row = base_opportunity()
    profile = _neutral_profile()
    result = evaluate_row(row, profile=profile)

    assert result["profile_score"] <= 59
    if result["lot_score"] >= 65:
        # Current layered policy allows lot score to reach REVIEW independently.
        # #472 owns the final semantic meaning of REVIEW; this test records the
        # threshold chain without declaring it customer relevance truth.
        assert result["decision"] == "REVIEW"
