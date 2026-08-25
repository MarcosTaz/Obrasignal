import copy

from intelligence_evaluation import evaluate_corpus, load_corpus


def test_synthetic_corpus_has_no_unexpected_invariant_violations():
    report = evaluate_corpus(load_corpus())

    assert report["dataset_size"] == 7
    assert report["label_counts"] == {
        "CLEAR_MATCH": 3,
        "CLEAR_NON_MATCH": 2,
        "INSUFFICIENT_INFORMATION": 1,
        "AMBIGUOUS": 1,
    }
    assert report["violations"] == []


def test_known_semantic_debt_is_visible_not_normalized_into_green_baseline():
    report = evaluate_corpus(load_corpus())

    assert {item["issue"] for item in report["known_debt"]} == {471, 472}
    assert {item["case"] for item in report["known_debt"]} == {
        "hard-negative-broad-cpv",
        "insufficient-information",
        "ambiguous-geography-only",
    }


def test_relevant_but_closed_keeps_fit_evidence_and_rejects_active_recommendation():
    report = evaluate_corpus(load_corpus())
    item = next(row for row in report["observations"] if row["id"] == "relevant-but-closed")

    assert item["positive_company_evidence"] is True
    assert item["decision"] == "REJECT"
    assert any("prazo de apresentação terminado" in blocker for blocker in item["hard_blockers"])


def test_hard_positive_outranks_controlled_hard_negative_without_absolute_score_oracle():
    report = evaluate_corpus(load_corpus())
    by_id = {row["id"]: row for row in report["observations"]}

    assert by_id["clear-match-pavilhao"]["profile_score"] > by_id["hard-negative-broad-cpv"]["profile_score"]
    assert by_id["hard-positive-specific-cpv"]["profile_score"] > by_id["insufficient-information"]["profile_score"]


def test_same_corpus_is_deterministic_and_fingerprint_stable():
    corpus = load_corpus()
    first = evaluate_corpus(copy.deepcopy(corpus))
    second = evaluate_corpus(copy.deepcopy(corpus))

    assert first["corpus_fingerprint"] == second["corpus_fingerprint"]
    assert first["observations"] == second["observations"]
    assert first["violations"] == second["violations"]


def test_harness_does_not_claim_unsupported_market_metrics():
    report = evaluate_corpus(load_corpus())

    forbidden = {"accuracy", "precision", "recall", "win_probability", "confidence_calibration"}
    assert forbidden.isdisjoint(report)
    assert any("not market precision/recall" in limitation for limitation in report["limitations"])
