import pytest

from customer_decision_intelligence import (
    TenantBoundaryError,
    build_decision_audit,
    company_state_input,
    decision_input,
    economics_input,
    evidence_input,
    learning_observation,
    outcome_input,
    pursuit_decision_input,
    readiness_input,
)


def _opportunity(**overrides):
    row = {
        "source": "PT_BASE",
        "external_id": "decision-001",
        "lifecycle_status": "OPEN",
        "lifecycle_reason": "publisher currently reports the procedure open",
        "deadline": "2026-09-30T12:00:00+00:00",
        "is_actionable": True,
    }
    row.update(overrides)
    return row


def _known_context(account_id="tenant-a", *, pursuit=None, outcome=None, company_fingerprint="company-v1"):
    return [
        evidence_input(
            {
                "state": "READY",
                "contract_version": "evidence.v1",
                "decision_claim_id": "claim-1",
                "missing_inputs": [],
            },
            account_id=account_id,
        ),
        company_state_input(
            {
                "account_id": account_id,
                "company_state_version": 7,
                "company_state_fingerprint": company_fingerprint,
                "unknowns": [],
                "conflicts": [],
                "facts": [{"private": "must-not-be-copied"}],
            },
            account_id=account_id,
        ),
        readiness_input(
            {
                "account_id": account_id,
                "status": "READY",
                "assessment_version": "opportunity-readiness.v0.2",
                "items": [],
            },
            account_id=account_id,
        ),
        economics_input(
            {
                "status": "FAVOURABLE",
                "reason": "known economic rules are satisfied",
                "rule_version": "economic-fit-v2",
            },
            account_id=account_id,
        ),
        pursuit_decision_input(pursuit, account_id=account_id),
        outcome_input(outcome, account_id=account_id),
    ]


def test_unknown_economic_score_never_becomes_known_or_zero_truth():
    item = economics_input(
        {
            "status": "UNKNOWN",
            "score": 0,
            "confidence": 0,
            "reason": "cost basis unavailable",
            "rule_version": "economic-fit-v2",
        },
        account_id="tenant-a",
    )

    assert item.truth_state == "UNKNOWN"
    assert dict(item.attributes)["status"] == "UNKNOWN"

    audit = build_decision_audit("tenant-a", _opportunity(), [item])
    assert audit["degraded_inputs"]["economics"] == "UNKNOWN"
    assert audit["action_support"]["PURSUE"]["decision_context"] == "DEGRADED"
    assert audit["action_support"]["PURSUE"]["state"] == "EXPLICIT_CUSTOMER_DECISION_REQUIRED"


def test_missing_pursuit_decision_is_not_no_bid_and_missing_outcome_is_not_lost():
    audit = build_decision_audit(
        "tenant-a",
        _opportunity(),
        _known_context(),
    )

    assert audit["explicit_pursuit_decision"] is None
    assert audit["current_outcome"] is None
    assert audit["action_support"]["DECLINE"]["state"] == "EXPLICIT_CUSTOMER_DECISION_REQUIRED"
    assert learning_observation(audit)["state"] == "INSUFFICIENT"


def test_no_bid_belongs_to_pursuit_journal_not_outcome_capture():
    pursuit = pursuit_decision_input(
        {"account_id": "tenant-a", "decision": "NO_BID", "decision_id": "d-1", "actor_type": "HUMAN"},
        account_id="tenant-a",
    )
    outcome = outcome_input(
        {"account_id": "tenant-a", "outcome_type": "NO_BID", "outcome_id": "o-invalid"},
        account_id="tenant-a",
    )

    assert pursuit.truth_state == "KNOWN"
    assert dict(pursuit.attributes)["decision"] == "NO_BID"
    assert outcome.truth_state == "UNKNOWN"
    assert dict(outcome.attributes)["outcome"] == "NO_BID"


def test_readiness_never_auto_promotes_to_pursue():
    audit = build_decision_audit(
        "tenant-a",
        _opportunity(),
        _known_context(),
    )

    assert audit["action_support"]["PURSUE"]["decision_context"] == "REVIEWABLE"
    assert audit["action_support"]["PURSUE"]["state"] == "EXPLICIT_CUSTOMER_DECISION_REQUIRED"


def test_explicit_human_pursue_is_recorded_but_not_manufactured_from_scores():
    audit = build_decision_audit(
        "tenant-a",
        _opportunity(),
        _known_context(
            pursuit={
                "account_id": "tenant-a",
                "decision": "PURSUE",
                "decision_id": "d-2",
                "actor_type": "HUMAN",
            }
        ),
    )

    assert audit["explicit_pursuit_decision"] == "PURSUE"
    assert audit["action_support"]["PURSUE"]["state"] == "RECORDED_EXPLICIT_DECISION"


def test_company_state_private_facts_are_not_copied_into_audit():
    audit = build_decision_audit(
        "tenant-a",
        _opportunity(),
        _known_context(),
    )

    serialized = repr(audit)
    assert "must-not-be-copied" not in serialized
    company = next(item for item in audit["inputs"] if item["name"] == "company_state")
    assert company["fingerprint"] == "company-v1"
    assert "facts" not in company


def test_company_state_conflict_remains_conflicted():
    item = company_state_input(
        {
            "account_id": "tenant-a",
            "company_state_version": 9,
            "company_state_fingerprint": "company-conflict",
            "unknowns": [],
            "conflicts": ["crew.available_count"],
        },
        account_id="tenant-a",
    )
    assert item.truth_state == "CONFLICTED"
    assert dict(item.attributes)["conflict_count"] == 1


def test_readiness_unknown_and_conflict_remain_visible():
    unknown = readiness_input(
        {
            "account_id": "tenant-a",
            "status": "UNKNOWN",
            "items": [{"status": "UNKNOWN", "code": "requirements_coverage_unverified"}],
        },
        account_id="tenant-a",
    )
    conflict = readiness_input(
        {
            "account_id": "tenant-a",
            "status": "UNKNOWN",
            "items": [{"status": "CONFLICT", "code": "certification_conflict"}],
        },
        account_id="tenant-a",
    )

    assert unknown.truth_state == "UNKNOWN"
    assert unknown.unknowns == ("requirements_coverage_unverified",)
    assert conflict.truth_state == "CONFLICTED"


def test_q080_unavailable_remains_unavailable_and_missing_inputs_stay_explicit():
    unavailable = evidence_input({"state": "UNAVAILABLE", "reason": "feature disabled"}, account_id="tenant-a")
    ready_partial = evidence_input(
        {
            "state": "READY",
            "contract_version": "evidence.v1",
            "decision_claim_id": "claim-2",
            "missing_inputs": ["value", "company_specialization"],
        },
        account_id="tenant-a",
    )

    assert unavailable.truth_state == "UNAVAILABLE"
    assert ready_partial.truth_state == "KNOWN"
    assert set(ready_partial.unknowns) == {"value", "company_specialization"}


def test_company_state_account_mismatch_fails_closed():
    with pytest.raises(TenantBoundaryError):
        company_state_input(
            {"account_id": "tenant-b", "company_state_fingerprint": "other"},
            account_id="tenant-a",
        )


def test_pursuit_and_outcome_account_mismatch_fail_closed():
    with pytest.raises(TenantBoundaryError):
        pursuit_decision_input({"account_id": "tenant-b", "decision": "PURSUE"}, account_id="tenant-a")
    with pytest.raises(TenantBoundaryError):
        outcome_input({"account_id": "tenant-b", "outcome_type": "WON"}, account_id="tenant-a")


def test_build_rejects_duplicate_inputs_and_cross_tenant_envelopes():
    one = decision_input("economics", "KNOWN", account_id="tenant-a")
    with pytest.raises(ValueError):
        build_decision_audit("tenant-a", _opportunity(), [one, one])

    foreign = decision_input("economics", "KNOWN", account_id="tenant-b")
    with pytest.raises(TenantBoundaryError):
        build_decision_audit("tenant-a", _opportunity(), [foreign])


def test_material_company_state_change_after_pursue_requires_review_without_rewriting_decision():
    pursuit = {
        "account_id": "tenant-a",
        "decision": "PURSUE",
        "decision_id": "decision-current",
        "actor_type": "HUMAN",
    }
    before = build_decision_audit(
        "tenant-a",
        _opportunity(),
        _known_context(pursuit=pursuit, company_fingerprint="company-v1"),
    )
    after = build_decision_audit(
        "tenant-a",
        _opportunity(),
        _known_context(pursuit=pursuit, company_fingerprint="company-v2"),
        previous_audit=before,
    )

    assert after["explicit_pursuit_decision"] == "PURSUE"
    assert after["change_impact"]["status"] == "REVIEW_REQUIRED"
    assert after["change_impact"]["review_required"] is True
    assert after["change_impact"]["historical_decision_preserved"] is True
    assert any(change["input"] == "company_state" for change in after["change_impact"]["material_changes"])


def test_stale_dependency_after_pursue_requires_review_even_without_recommendation_flip():
    pursuit = {
        "account_id": "tenant-a",
        "decision": "PURSUE",
        "decision_id": "decision-current",
        "actor_type": "HUMAN",
    }
    before = build_decision_audit("tenant-a", _opportunity(), _known_context(pursuit=pursuit))
    current_inputs = _known_context(pursuit=pursuit)
    current_inputs = [item for item in current_inputs if item.name != "economics"]
    current_inputs.append(decision_input("economics", "STALE", account_id="tenant-a", version="economics-v2"))

    after = build_decision_audit("tenant-a", _opportunity(), current_inputs, previous_audit=before)

    assert after["degraded_inputs"]["economics"] == "STALE"
    assert after["change_impact"]["review_required"] is True
    assert after["action_support"]["PURSUE"]["state"] == "RECORDED_EXPLICIT_DECISION"


def test_outcome_correction_does_not_rewrite_historical_decision():
    pursuit = {
        "account_id": "tenant-a",
        "decision": "PURSUE",
        "decision_id": "decision-current",
        "actor_type": "HUMAN",
    }
    won = {"account_id": "tenant-a", "outcome_type": "WON", "outcome_id": "outcome-1"}
    lost = {"account_id": "tenant-a", "outcome_type": "LOST", "outcome_id": "outcome-2"}
    before = build_decision_audit("tenant-a", _opportunity(), _known_context(pursuit=pursuit, outcome=won))
    after = build_decision_audit("tenant-a", _opportunity(), _known_context(pursuit=pursuit, outcome=lost), previous_audit=before)

    assert after["explicit_pursuit_decision"] == "PURSUE"
    assert after["current_outcome"] == "LOST"
    assert after["change_impact"]["historical_decision_preserved"] is True


def test_learning_pair_never_establishes_causality_or_enables_model_update():
    audit = build_decision_audit(
        "tenant-a",
        _opportunity(),
        _known_context(
            pursuit={"account_id": "tenant-a", "decision": "PURSUE", "decision_id": "d-3", "actor_type": "HUMAN"},
            outcome={"account_id": "tenant-a", "outcome_type": "WON", "outcome_id": "o-3"},
        ),
    )

    observation = learning_observation(audit)
    assert observation == {
        "state": "OBSERVED_PAIR",
        "decision": "PURSUE",
        "outcome": "WON",
        "causal_attribution": "NOT_ESTABLISHED",
        "model_update_allowed": False,
        "reason": "explicit decision and observed outcome are both available",
    }


def test_invalid_truth_state_and_missing_identity_fail_closed():
    with pytest.raises(ValueError):
        decision_input("economics", "GOOD")
    with pytest.raises(ValueError):
        build_decision_audit("tenant-a", {"source": "PT_BASE"}, [])
