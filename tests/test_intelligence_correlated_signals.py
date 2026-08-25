from commercial_score_v2 import score_v2
from intelligence_counterfactual_audit import base_opportunity, base_profile
from profile_scoring import personalized_score


def _personalized(row, profile):
    commercial = score_v2(row)["score"]
    return personalized_score(row, base_score=commercial, profile=profile)[0]


def test_cpv_business_fact_contributes_at_both_commercial_and_profile_layers():
    row = base_opportunity()
    profile = base_profile()

    both = _personalized(row, profile)

    commercial_only_profile = dict(profile)
    commercial_only_profile["cpv_prefixes"] = []
    commercial_only = _personalized(row, commercial_only_profile)

    neither_row = dict(row)
    neither_row["cpv"] = "79900000"
    neither = _personalized(neither_row, commercial_only_profile)

    # The same CPV value contributes once to the base commercial score and a
    # second time to account-specific profile fit. This is measured overlap,
    # not proof that either contribution is wrong.
    assert both > commercial_only > neither
    assert both - commercial_only == 10
    assert commercial_only - neither > 0


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
