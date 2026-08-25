import pytest

from customer_decision_metrics import decision_metrics


def _audit(*, decision=None, outcome=None, states=None, account="tenant-a", external_id="opp-1"):
    states = states or {}
    inputs = []
    for name in ("source_truth", "evidence", "company_state", "readiness", "economics"):
        inputs.append({"name": name, "truth_state": states.get(name, "KNOWN")})
    return {
        "account_id": account,
        "opportunity": {"source": "TED", "external_id": external_id},
        "inputs": inputs,
        "explicit_pursuit_decision": decision,
        "current_outcome": outcome,
    }


def test_metrics_do_not_invent_review_or_usefulness_rates():
    result = decision_metrics([_audit(decision="PURSUE", outcome="WON")])
    assert result["useful_opportunities_surfaced"]["state"] == "UNAVAILABLE"
    assert result["review_to_pursuit"]["state"] == "UNAVAILABLE"
    assert result["review_to_decline"]["state"] == "UNAVAILABLE"
    assert result["decision_reversal_rate"]["state"] == "UNAVAILABLE"
    assert result["optimization_allowed"] is False


def test_missing_outcome_is_not_captured_or_loss():
    result = decision_metrics([_audit(decision="PURSUE", outcome=None)])
    metric = result["outcome_capture_completeness"]
    assert metric["state"] == "KNOWN"
    assert metric["numerator"] == 0
    assert metric["denominator"] == 1
    assert metric["rate"] == 0


def test_no_decisions_means_outcome_metric_unavailable_not_zero_percent():
    result = decision_metrics([_audit(decision=None, outcome=None)])
    metric = result["outcome_capture_completeness"]
    assert metric["state"] == "UNAVAILABLE"
    assert metric["rate"] is None


def test_unknown_stale_unavailable_and_conflict_are_distinct():
    result = decision_metrics([
        _audit(
            decision="PURSUE",
            outcome="BID_SUBMITTED",
            states={
                "evidence": "UNKNOWN",
                "company_state": "STALE",
                "readiness": "UNAVAILABLE",
                "economics": "CONFLICTED",
            },
        )
    ])
    assert result["truth_state_counts"] == {
        "UNKNOWN": 1,
        "STALE": 1,
        "UNAVAILABLE": 1,
        "CONFLICTED": 1,
    }
    assert result["unknown_data_rate"]["rate"] == pytest.approx(1 / 5)
    assert result["degraded_input_rate"]["rate"] == pytest.approx(4 / 5)
    assert result["stale_decision_exposure"]["rate"] == 1
    assert result["degraded_decision_exposure"]["rate"] == 1


def test_known_envelope_with_explicit_unknown_subinputs_is_unknown_exposure():
    audit = _audit(decision="PURSUE", outcome="BID_SUBMITTED")
    evidence = next(item for item in audit["inputs"] if item["name"] == "evidence")
    evidence["unknowns"] = ["value", "company_specialization"]

    result = decision_metrics([audit])

    assert result["truth_state_counts"]["UNKNOWN"] == 0
    assert result["explicit_unknown_subinputs"] == 2
    assert result["unknown_exposure_slots"] == 1
    assert result["unknown_data_rate"]["rate"] == pytest.approx(1 / 5)
    assert result["degraded_input_rate"]["rate"] == pytest.approx(1 / 5)
    assert result["degraded_decision_exposure"]["rate"] == 1


def test_missing_critical_input_counts_unavailable_not_unknown():
    audit = _audit(decision="NO_BID", outcome="NO_SUBMISSION")
    audit["inputs"] = [item for item in audit["inputs"] if item["name"] != "economics"]
    result = decision_metrics([audit])
    assert result["truth_state_counts"]["UNAVAILABLE"] == 1
    assert result["truth_state_counts"]["UNKNOWN"] == 0


def test_duplicate_current_audits_fail_instead_of_double_counting():
    row = _audit(decision="PURSUE", outcome="WON")
    with pytest.raises(ValueError, match="one current audit"):
        decision_metrics([row, row])


def test_tenant_identity_is_part_of_metric_identity():
    result = decision_metrics([
        _audit(decision="PURSUE", outcome="WON", account="tenant-a"),
        _audit(decision="NO_BID", outcome="NO_SUBMISSION", account="tenant-b"),
    ])
    assert result["audited_opportunities"] == 2
    assert result["explicit_decisions"] == 2
    assert result["decision_counts"] == {"NO_BID": 1, "PURSUE": 1}
