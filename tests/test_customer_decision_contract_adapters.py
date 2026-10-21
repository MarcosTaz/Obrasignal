from customer_decision_intelligence import company_state_input, readiness_input


def test_readiness_adapter_consumes_public_unknown_items_contract():
    item = readiness_input(
        {
            "account_id": "tenant-a",
            "overall_status": "UNKNOWN",
            "assessment_version": "opportunity-readiness.v0.2",
            "unknown_items": [
                {
                    "code": "submission_deadline_precision_insufficient",
                    "status": "UNKNOWN",
                    "critical": True,
                }
            ],
            "conflict_items": [],
        },
        account_id="tenant-a",
    )

    assert item.truth_state == "UNKNOWN"
    assert item.unknowns == ("submission_deadline_precision_insufficient",)
    assert dict(item.attributes)["overall_status"] == "UNKNOWN"


def test_readiness_adapter_consumes_public_conflict_items_contract():
    item = readiness_input(
        {
            "account_id": "tenant-a",
            "overall_status": "UNKNOWN",
            "assessment_version": "opportunity-readiness.v0.2",
            "unknown_items": [],
            "conflict_items": [
                {
                    "code": "requirement_conflict",
                    "status": "CONFLICT",
                    "critical": True,
                }
            ],
        },
        account_id="tenant-a",
    )

    assert item.truth_state == "CONFLICTED"


def test_company_state_empty_known_fact_set_with_explicit_unknowns_is_unknown():
    item = company_state_input(
        {
            "account_id": "tenant-a",
            "contract_version": "company-state.v1",
            "company_state_version": 4,
            "company_state_fingerprint": "state-4",
            "facts": [],
            "unknowns": ["crew.available_count", "certification.current_validity"],
            "conflicts": [],
        },
        account_id="tenant-a",
    )

    assert item.truth_state == "UNKNOWN"
    assert set(item.unknowns) == {"crew.available_count", "certification.current_validity"}
