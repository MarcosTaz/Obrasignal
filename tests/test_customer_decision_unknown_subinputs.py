from customer_decision_intelligence import (
    build_decision_audit,
    decision_input,
    evidence_input,
    pursuit_decision_input,
)


def test_ready_evidence_with_missing_inputs_degrades_decision_context():
    audit = build_decision_audit(
        "tenant-a",
        {"source": "PT_BASE", "external_id": "opp-1", "lifecycle_status": "OPEN", "is_actionable": True},
        [
            evidence_input(
                {
                    "state": "READY",
                    "contract_version": "evidence.v1",
                    "decision_claim_id": "claim-1",
                    "missing_inputs": ["value", "company_specialization"],
                },
                account_id="tenant-a",
            ),
            decision_input("company_state", "KNOWN", account_id="tenant-a"),
            decision_input("readiness", "KNOWN", account_id="tenant-a"),
            decision_input("economics", "KNOWN", account_id="tenant-a"),
        ],
    )

    evidence = next(item for item in audit["inputs"] if item["name"] == "evidence")
    assert evidence["truth_state"] == "KNOWN"
    assert evidence["unknowns"] == ["value", "company_specialization"]
    assert audit["degraded_inputs"]["evidence"] == "UNKNOWN"
    assert audit["action_support"]["PURSUE"]["decision_context"] == "DEGRADED"
    assert audit["action_support"]["DECLINE"]["decision_context"] == "DEGRADED"


def test_existing_pursue_is_preserved_but_re_review_required_when_unknowns_appear():
    opportunity = {"source": "PT_BASE", "external_id": "opp-2", "lifecycle_status": "OPEN", "is_actionable": True}
    pursuit = pursuit_decision_input(
        {"account_id": "tenant-a", "decision": "PURSUE", "decision_id": "d-1", "actor_type": "HUMAN"},
        account_id="tenant-a",
    )
    baseline = build_decision_audit(
        "tenant-a",
        opportunity,
        [
            decision_input("evidence", "KNOWN", account_id="tenant-a"),
            decision_input("company_state", "KNOWN", account_id="tenant-a"),
            decision_input("readiness", "KNOWN", account_id="tenant-a"),
            decision_input("economics", "KNOWN", account_id="tenant-a"),
            pursuit,
        ],
    )
    current = build_decision_audit(
        "tenant-a",
        opportunity,
        [
            decision_input("evidence", "KNOWN", account_id="tenant-a", unknowns=("value",)),
            decision_input("company_state", "KNOWN", account_id="tenant-a"),
            decision_input("readiness", "KNOWN", account_id="tenant-a"),
            decision_input("economics", "KNOWN", account_id="tenant-a"),
            pursuit,
        ],
        previous_audit=baseline,
    )

    assert current["explicit_pursuit_decision"] == "PURSUE"
    assert current["action_support"]["PURSUE"]["state"] == "RECORDED_EXPLICIT_DECISION"
    assert current["change_impact"]["status"] == "REVIEW_REQUIRED"
    assert current["change_impact"]["historical_decision_preserved"] is True
