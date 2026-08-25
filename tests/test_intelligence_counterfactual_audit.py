from intelligence_counterfactual_audit import (
    commercial_counterfactual,
    personalized_counterfactual,
    pipeline_counterfactual,
    run_feature_dominance_audit,
)


def test_commercial_cpv_counterfactual_changes_cpv_component_without_mutating_other_components():
    result = commercial_counterfactual("cpv", "79900000")
    changed = {key for key, delta in result["component_delta"].items() if delta}
    assert changed == {"cpv_fit"}
    assert result["delta"] < 0


def test_commercial_value_counterfactual_changes_only_size_component():
    result = commercial_counterfactual("value", 6_000_000)
    changed = {key for key, delta in result["component_delta"].items() if delta}
    assert changed == {"size_fit"}
    assert result["delta"] < 0


def test_commercial_procedure_counterfactual_changes_only_access_component():
    result = commercial_counterfactual("procedure_type", "restricted procedure")
    changed = {key for key, delta in result["component_delta"].items() if delta}
    assert changed == {"access"}
    assert result["delta"] < 0
    assert any("procedimento" in reason for reason in result["reason_delta"]["added"])


def test_expired_deadline_is_separated_as_actionability_effect_in_pipeline():
    result = pipeline_counterfactual("deadline", "2000-01-01T12:00:00+00:00")
    assert result["actionability_impact"] is True
    assert result["new_decision"] == "REJECT"
    assert result["new_score"] <= 35
    assert any("prazo de apresentação terminado" in blocker for blocker in result["hard_blockers_after"])


def test_out_of_range_value_cap_is_not_mislabeled_as_confidence():
    result = pipeline_counterfactual("value", 6_000_000)
    assert result["actionability_impact"] is True
    assert result["new_score"] <= 35
    assert any("valor acima do máximo" in blocker for blocker in result["hard_blockers_after"])


def test_profile_keyword_counterfactual_does_not_change_commercial_or_lot_score():
    result = pipeline_counterfactual("profile.keywords", ["pintura industrial"])
    assert result["lot_delta"] == 0
    assert result["new_lot_score"] == result["base_lot_score"]


def test_personalized_country_reason_tracks_country_signal():
    result = personalized_counterfactual("country", "ESP")
    assert result["delta"] < 0
    assert "mercado preferido" in result["reason_delta"]["removed"]


def test_audit_is_structural_evidence_not_market_importance_or_probability():
    report = run_feature_dominance_audit()
    serialized = repr(report).lower()
    assert report["status"] == "SYNTHETIC_COUNTERFACTUAL_ONLY"
    assert "not market feature importance" in " ".join(report["limitations"])
    assert "win_probability" not in serialized
    assert "relevance_probability" not in serialized
    assert "calibrated_confidence" not in serialized
