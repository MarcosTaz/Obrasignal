from pathlib import Path

from intelligence_evaluation import evaluate_corpus, load_corpus


CORPUS = Path(__file__).with_name("fixtures") / "intelligence_evaluation_pt_v2.json"


def test_portuguese_corpus_v2_has_expected_nonbinary_label_coverage_and_no_unexpected_violations():
    report = evaluate_corpus(load_corpus(CORPUS))

    assert report["dataset_size"] == 8
    assert report["label_counts"] == {
        "CLEAR_MATCH": 5,
        "CLEAR_NON_MATCH": 1,
        "AMBIGUOUS": 1,
        "INSUFFICIENT_INFORMATION": 1,
    }
    assert report["violations"] == []
    assert {item["issue"] for item in report["known_debt"]} == {471, 472}


def test_hard_positive_uses_specific_cpv_without_obvious_keyword_text():
    report = evaluate_corpus(load_corpus(CORPUS))
    by_id = {item["id"]: item for item in report["observations"]}

    item = by_id["pt-hard-positive-cpv-generic-text"]
    assert item["positive_company_evidence"] is True
    assert item["cpv_strength"] == "STRONG"
    assert item["profile_score"] > by_id["pt-hard-negative-sobras"]["profile_score"]


def test_hard_negative_surface_overlap_does_not_match_obras_inside_sobras():
    report = evaluate_corpus(load_corpus(CORPUS))
    item = next(row for row in report["observations"] if row["id"] == "pt-hard-negative-sobras")

    assert item["positive_company_evidence"] is False
    assert item["decision"] == "REJECT"


def test_accent_equivalent_portuguese_cases_preserve_positive_fit_evidence():
    report = evaluate_corpus(load_corpus(CORPUS))
    by_id = {item["id"]: item for item in report["observations"]}

    assert by_id["pt-avac-accent-clear-match"]["positive_company_evidence"] is True
    assert by_id["pt-eletrica-accent-clear-match"]["positive_company_evidence"] is True


def test_ambiguous_and_insufficient_cases_are_not_relabelled_as_clear_nonmatches():
    corpus = load_corpus(CORPUS)
    labels = {case["id"]: case["label"] for case in corpus["cases"]}

    assert labels["pt-manutencao-ambiguous"] == "AMBIGUOUS"
    assert labels["pt-insufficient-metadata"] == "INSUFFICIENT_INFORMATION"


def test_portuguese_corpus_still_makes_no_market_quality_or_probability_claim():
    report = evaluate_corpus(load_corpus(CORPUS))

    forbidden = {"accuracy", "precision", "recall", "calibration", "win_probability", "bid_probability"}
    assert forbidden.isdisjoint(report)
    assert any("not market precision/recall" in text for text in report["limitations"])
