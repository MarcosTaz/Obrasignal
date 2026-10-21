from intelligence_counterfactual_audit import base_opportunity, base_profile
from intelligence_reason_fidelity_audit import (
    commercial_reason_counterfactual,
    detect_unsupported_positive_explanations,
    explanation_provenance,
    personalized_reason_counterfactual,
)
from opportunity_match_pipeline import evaluate_row


def test_cpv_reason_changes_when_cpv_contribution_is_removed():
    result = commercial_reason_counterfactual("cpv", "79900000")
    assert result["score_delta"] != 0
    assert result["reason_delta"]["removed"]
    assert result["classification"] == "SCORE_CHANGED_REASON_CHANGED_FAITHFULLY"


def test_procedure_reason_tracks_restricted_access_change():
    result = commercial_reason_counterfactual("procedure_type", "restricted procedure")
    assert result["score_delta"] != 0
    assert any("procedimento com acesso mais exigente" in reason for reason in result["reason_delta"]["added"])
    assert result["classification"] == "SCORE_CHANGED_REASON_CHANGED_FAITHFULLY"


def test_profile_keyword_reason_is_removed_when_profile_keyword_support_disappears():
    result = personalized_reason_counterfactual("profile.keywords", ["pintura industrial"])
    assert result["score_delta"] < 0
    assert any(reason.startswith("perfil:") for reason in result["reason_delta"]["removed"])


def test_same_score_does_not_define_reason_identity():
    a = base_opportunity()
    b = base_opportunity()
    # Different semantic causes can converge at the same bounded score; reason
    # truth must still come from the actual features rather than the number.
    b["procedure_type"] = "restricted procedure"
    b["deadline"] = "2099-12-31T12:00:00+00:00"
    ea = evaluate_row(a, profile=base_profile())
    eb = evaluate_row(b, profile=base_profile())
    if ea["profile_score"] == eb["profile_score"]:
        assert ea["reason"] != eb["reason"] or ea["commercial"]["reasons"] != eb["commercial"]["reasons"]


def test_blocked_evaluation_detects_generic_positive_placeholders():
    row = base_opportunity()
    row["cpv"] = "79900000"
    evaluation = evaluate_row(row, profile=base_profile())
    assert evaluation["hard_capability_blockers"]
    findings = detect_unsupported_positive_explanations(evaluation)
    classes = {finding["classification"] for finding in findings}
    assert "UNSUPPORTED_POSITIVE_CLAIM" in classes


def test_reason_provenance_graph_keeps_source_rule_and_effect_separate():
    evaluation = evaluate_row(base_opportunity(), profile=base_profile())
    graph = explanation_provenance(evaluation)
    assert {item["reason_key"] for item in graph} >= {"profile", "lot", "cpv", "capability", "geography", "economic_fit"}
    for item in graph:
        assert item["source_feature"]
        assert item["rule"]
        assert "score_effect" in item
        assert "support_state" in item
