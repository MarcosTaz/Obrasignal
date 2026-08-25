import pytest

from analytics_quality import (
    metric_contracts,
    rate_contract,
    validate_event_metadata,
    validate_metric_contracts,
)


def test_every_metric_exposes_version_retention_deletion_export_and_privacy():
    assert validate_metric_contracts() is True
    contracts = metric_contracts()
    assert contracts
    for contract in contracts.values():
        assert contract["measurement_schema_version"]
        assert contract["quality_schema_version"]
        assert contract["retention"]["status"] in {"PROVEN", "UNKNOWN"}
        assert contract["deletion_export"]["status"] in {"PROVEN", "UNKNOWN"}
        assert contract["privacy"]["raw_customer_or_procurement_payload"] == "FORBIDDEN"


def test_current_retention_unknown_is_not_invented_as_a_default_period():
    for contract in metric_contracts().values():
        assert contract["retention"]["status"] == "UNKNOWN"
        assert "30" not in contract["retention"]["reason"]
        assert "days" not in contract["retention"]["reason"].lower()


def test_privacy_guard_accepts_minimal_technical_metadata():
    assert validate_event_metadata({
        "source": "TED",
        "external_id": "123",
        "workflow_status": "REVIEWING",
    }) == {
        "source": "TED",
        "external_id": "123",
        "workflow_status": "REVIEWING",
    }


@pytest.mark.parametrize(
    "metadata",
    [
        {"token": "secret"},
        {"email": "person@example.test"},
        {"title": "raw tender title"},
        {"buyer": "buyer name"},
        {"note": "customer private note"},
        {"profile_text": "private profile"},
        {"payload": "raw"},
        {"request_body": "raw"},
    ],
)
def test_privacy_guard_rejects_sensitive_or_raw_payload_keys(metadata):
    with pytest.raises(ValueError):
        validate_event_metadata(metadata)


def test_privacy_guard_rejects_unapproved_and_nested_metadata():
    with pytest.raises(ValueError, match="unapproved_key"):
        validate_event_metadata({"campaign_name": "x"})
    with pytest.raises(ValueError, match="nested_value_forbidden"):
        validate_event_metadata({"reason_code": {"nested": "x"}})


def test_rate_contract_requires_numerator_denominator_eligibility_and_missing_policy():
    contract = rate_contract(
        numerator="paid eligible accounts",
        denominator="Evaluation-activated eligible accounts",
        eligibility="same cohort and observation window",
        missing_behavior="RATE_UNKNOWN when billing or eligibility state is unverified",
    )
    assert contract["zero_denominator_behavior"] == "RATE_UNKNOWN"
    assert contract["unknown_data_behavior"].endswith("RATE_UNKNOWN")

    with pytest.raises(ValueError):
        rate_contract(
            numerator="paid",
            denominator="",
            eligibility="same cohort",
            missing_behavior="unknown stays unknown",
        )
