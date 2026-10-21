import pytest

from intelligence_rank_counterfactual_audit import _rank_unique, controlled_candidate_set, rank_counterfactual


def test_controlled_candidate_set_has_unique_scores_for_rank_measurement():
    items, _ = controlled_candidate_set()
    scores = [item["score"] for item in items]
    assert len(scores) == len(set(scores))


def test_tie_policy_is_not_invented_by_counterfactual_harness():
    with pytest.raises(ValueError, match="TIE_REQUIRES_SEPARATE_AUTHORITY_AUDIT"):
        _rank_unique([
            {"external_id": "a", "score": 70},
            {"external_id": "b", "score": 70},
        ])


def test_cpv_change_records_score_rank_and_reason_chain():
    result = rank_counterfactual("cpv", "79900000", k=2)
    assert result["score_delta"] != 0
    assert result["reason_changed"]
    assert result["old_rank"] != result["new_rank"] or result["classification"] == "NO_RANK_EFFECT"
    assert result["classification"] in {"EXPECTED_RANK_MOVE", "TOP_K_BOUNDARY_FLIP", "NO_RANK_EFFECT"}


def test_top_k_flags_match_membership_transition():
    result = rank_counterfactual("country", "ESP", k=2)
    before = "subject" in result["top_k_before"]
    after = "subject" in result["top_k_after"]
    assert result["top_k_entry"] == (not before and after)
    assert result["top_k_exit"] == (before and not after)


def test_top_k_movement_is_not_labeled_as_correctness():
    result = rank_counterfactual("value_numeric", 6_000_000, k=2)
    assert "correct" not in result["classification"].casefold()
