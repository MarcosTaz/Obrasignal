from datetime import datetime, timezone

import pytest

from analytics_learning import experiment_contract, is_learning_stale, learning_record


def test_experiment_requires_falsifiable_population_metric_guardrails_and_decision_rule():
    contract = experiment_contract(
        hypothesis="Showing source freshness reduces abandonment before first shortlist",
        population="new authenticated Web accounts with usable source coverage",
        primary_metric="profile-to-first-shortlist progression under a complete measurement contract",
        guardrails=["product truth cannot weaken", "privacy and tenant isolation cannot weaken"],
        duration="14 days or predeclared eligible sample boundary",
        decision_rule="ship only if primary metric improves without guardrail regression",
        owner="Data/Analytics + Web acceptance",
    )
    assert contract["dark_patterns"] == "FORBIDDEN"
    assert contract["security_or_truth_weakening"] == "FORBIDDEN"
    assert contract["causality_claim"].startswith("NOT_ESTABLISHED")


def test_experiment_rejects_missing_truth_or_privacy_security_guardrails():
    with pytest.raises(ValueError, match="guard_product_truth"):
        experiment_contract(
            hypothesis="x",
            population="eligible accounts",
            primary_metric="metric",
            guardrails=["revenue cannot decrease"],
            duration="7 days",
            decision_rule="predeclared rule",
            owner="Analytics",
        )


def test_proven_signal_and_disproven_learning_require_evidence():
    for state in ("PROVEN", "SIGNAL", "DISPROVEN"):
        with pytest.raises(ValueError, match="requires_evidence"):
            learning_record(
                state=state,
                claim="claim",
                observed_at="2026-08-25T10:00:00+00:00",
                source_owner="owner",
                decision_use="decision",
            )


def test_assumption_remains_explicit_without_evidence():
    record = learning_record(
        state="ASSUMPTION",
        claim="alerts may improve useful return",
        observed_at="2026-08-25T10:00:00+00:00",
        source_owner="Product Strategy",
        decision_use="decide whether alert-return instrumentation is worth prioritizing",
    )
    assert record["state"] == "ASSUMPTION"
    assert record["evidence_refs"] == []
    assert record["causality"] == "NOT_CLAIMED"


def test_proven_does_not_automatically_claim_causality():
    record = learning_record(
        state="PROVEN",
        claim="one eligible tenant completed the measured activation sequence",
        evidence_refs=["github:#333", "golden:activation-proof"],
        observed_at="2026-08-25T10:00:00+00:00",
        source_owner="Evaluation/Golden",
        decision_use="allow Analytics to include the observed sequence as measured evidence",
    )
    assert record["causality"] == "REQUIRES_SEPARATE_CAUSAL_EVIDENCE"


def test_learning_staleness_requires_explicit_review_boundary():
    no_review = learning_record(
        state="UNKNOWN",
        claim="retention policy",
        observed_at="2026-08-25T10:00:00+00:00",
        source_owner="Account/Privacy",
        decision_use="analytics storage decision",
    )
    assert is_learning_stale(no_review, now=datetime(2030, 1, 1, tzinfo=timezone.utc)) is False

    reviewed = learning_record(
        state="SIGNAL",
        claim="a measured friction pattern may be recurring",
        evidence_refs=["measurement:cohort-001"],
        observed_at="2026-08-25T10:00:00+00:00",
        review_at="2026-09-01T10:00:00+00:00",
        source_owner="Analytics",
        decision_use="revalidate before roadmap promotion",
    )
    assert is_learning_stale(reviewed, now=datetime(2026, 9, 2, tzinfo=timezone.utc)) is True
