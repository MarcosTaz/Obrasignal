from commercial_score_v2 import score_v2
from intelligence_counterfactual_audit import base_opportunity, base_profile
from profile_scoring import personalized_score


def _personalized(row, profile, *, base_score=None):
    commercial = score_v2(row)["score"] if base_score is None else base_score
    return personalized_score(row, base_score=commercial, profile=profile)[0]


def test_cpv_business_fact_contributes_at_both_commercial_and_profile_layers():
    row = base_opportunity()
    profile = base_profile()

    # Measure the profile-layer CPV contribution below the 100 ceiling so score
    # clipping cannot hide part of the configured contribution.
    profile_both = _personalized(row, profile, base_score=50)
    commercial_only_profile = dict(profile)
    commercial_only_profile["cpv_prefixes"] = []
    profile_without_cpv = _personalized(row, commercial_only_profile, base_score=50)
    assert profile_both - profile_without_cpv == 10

    # Measure the commercial-layer contribution independently, preserving every
    # other opportunity input. This establishes overlap without adding the two
    # layers into a saturated score and pretending the clipped delta is causal.
    commercial_with_cpv = score_v2(row)["score"]
    no_cpv_row = dict(row)
    no_cpv_row["cpv"] = "79900000"
    commercial_without_cpv = score_v2(no_cpv_row)["score"]
    assert commercial_with_cpv > commercial_without_cpv


def test_personalized_score_ceiling_is_a_discontinuous_effect_for_cpv_measurement():
    row = base_opportunity()
    profile = base_profile()
    without_profile_cpv = dict(profile)
    without_profile_cpv["cpv_prefixes"] = []

    unclipped_contribution = _personalized(row, profile, base_score=50) - _personalized(
        row, without_profile_cpv, base_score=50
    )
    observed_at_current_commercial_base = _personalized(row, profile) - _personalized(
        row, without_profile_cpv
    )

    assert unclipped_contribution == 10
    assert observed_at_current_commercial_base < unclipped_contribution
    assert _personalized(row, profile) == 100


def test_text_business_fact_can_contribute_to_commercial_and_profile_layers_separately():
    row = base_opportunity()
    profile = base_profile()
    both = _personalized(row, profile)

    no_profile_text = dict(profile)
    no_profile_text["keywords"] = ["pintura industrial"]
    commercial_text_only = _personalized(row, no_profile_text)

    no_text_row = dict(row)
    no_text_row["title"] = "Aquisição de equipamento"
    no_text_row["description"] = "Fornecimento previsto no caderno de encargos"
    neither = _personalized(no_text_row, no_profile_text)

    assert both > commercial_text_only
    assert commercial_text_only >= neither


def test_correlated_signal_measurement_does_not_assert_market_importance():
    # Guardrail: these regressions preserve observed rule composition only.
    # Whether overlap is intentional layered policy or DOUBLE_COUNT_RISK is a
    # semantic/product decision after measured evidence, not a weight inference.
    assert True
