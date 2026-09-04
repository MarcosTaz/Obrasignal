import pytest

from vertical_apps.industrial_claims.leakage_reconciliation import (
    LeakageReconciliationError,
    reconcile_recovery_ledger,
)


def test_reconciliation_separates_evidence_claim_approval_and_settlement_gaps():
    result = reconcile_recovery_ledger(
        documented_cost="120000",
        mitigation="20000",
        evidence_supported="80000",
        claimed="65000",
        approved="50000",
        settled="30000",
        currency="EUR",
    )

    assert result.net_documented_exposure == 100000
    assert result.unsupported_exposure == 20000
    assert result.supported_unclaimed == 15000
    assert result.claimed_unapproved == 15000
    assert result.approved_unsettled == 20000
    assert result.supported_unsettled == 50000
    assert result.signals == (
        "EVIDENCE_GAP",
        "SUPPORTED_UNCLAIMED",
        "CLAIM_DECISION_GAP",
        "APPROVED_UNSETTLED",
    )
    assert len(result.reconciliation_hash) == 64


def test_reconciliation_never_promotes_unsupported_cost_to_claimable_value():
    result = reconcile_recovery_ledger(
        documented_cost="90000",
        mitigation="10000",
        evidence_supported="0",
        claimed="0",
        approved="0",
        settled="0",
        currency="EUR",
    )

    assert result.net_documented_exposure == 80000
    assert result.supported_unsettled == 0
    assert result.signals == ("EVIDENCE_GAP",)


def test_fully_reconciled_requires_supported_value_to_be_settled():
    result = reconcile_recovery_ledger(
        documented_cost="50000",
        mitigation="0",
        evidence_supported="50000",
        claimed="50000",
        approved="50000",
        settled="50000",
        currency="usd",
    )

    assert result.signals == ("FULLY_RECONCILED",)
    assert result.currency == "USD"
    assert result.supported_unsettled == 0


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"mitigation": "100001"}, "mitigation cannot exceed documented cost"),
        ({"evidence_supported": "100001"}, "evidence-supported amount cannot exceed net documented exposure"),
        ({"claimed": "80001"}, "claimed amount cannot exceed evidence-supported amount"),
        ({"approved": "65001"}, "approved amount cannot exceed claimed amount"),
        ({"settled": "50001"}, "settled amount cannot exceed approved amount"),
    ],
)
def test_impossible_recovery_ledgers_fail_closed(overrides, message):
    values = {
        "documented_cost": "120000",
        "mitigation": "20000",
        "evidence_supported": "80000",
        "claimed": "65000",
        "approved": "50000",
        "settled": "30000",
        "currency": "EUR",
    }
    values.update(overrides)

    with pytest.raises(LeakageReconciliationError, match=message):
        reconcile_recovery_ledger(**values)


def test_negative_nonfinite_and_invalid_currency_are_rejected():
    with pytest.raises(LeakageReconciliationError):
        reconcile_recovery_ledger(
            documented_cost="NaN",
            evidence_supported="0",
            claimed="0",
            approved="0",
            settled="0",
            currency="EUR",
        )
    with pytest.raises(LeakageReconciliationError):
        reconcile_recovery_ledger(
            documented_cost="1",
            evidence_supported="0",
            claimed="0",
            approved="0",
            settled="0",
            currency="EURO",
        )


def test_reconciliation_hash_is_deterministic_and_changes_with_economic_state():
    base = dict(
        documented_cost="100",
        mitigation="10",
        evidence_supported="80",
        claimed="70",
        approved="60",
        settled="50",
        currency="EUR",
    )
    first = reconcile_recovery_ledger(**base)
    second = reconcile_recovery_ledger(**base)
    changed = reconcile_recovery_ledger(**{**base, "settled": "51"})

    assert first.reconciliation_hash == second.reconciliation_hash
    assert first.reconciliation_hash != changed.reconciliation_hash
