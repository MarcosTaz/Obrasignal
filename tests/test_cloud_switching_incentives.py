from decimal import Decimal

import pytest

from cloud_switching.incentives import Incentive, IncentiveStatus, total_captured_value

D = Decimal


def test_potential_incentive_is_not_counted_as_captured_value():
    incentive = Incentive(
        incentive_id="aws-map-1",
        program="AWS MAP",
        status=IncentiveStatus.POTENTIAL,
        potential_amount=D("50000"),
    )
    assert incentive.captured_value() == D("0")


def test_approved_but_unreceived_incentive_is_not_counted():
    incentive = Incentive(
        incentive_id="gcp-ramp-1",
        program="Google RaMP",
        status=IncentiveStatus.APPROVED,
        potential_amount=D("80000"),
        approved_amount=D("60000"),
        approval_evidence_id="approval-1",
    )
    assert incentive.captured_value() == D("0")


def test_partial_receipt_counts_only_received_value():
    incentive = Incentive(
        incentive_id="gcp-ramp-2",
        program="Google RaMP",
        status=IncentiveStatus.PARTIALLY_RECEIVED,
        approved_amount=D("60000"),
        received_amount=D("25000"),
        approval_evidence_id="approval-2",
        receipt_evidence_id="credit-memo-1",
    )
    assert incentive.captured_value() == D("25000")


def test_received_value_cannot_exceed_approved_value():
    incentive = Incentive(
        incentive_id="bad",
        program="Bad input",
        status=IncentiveStatus.PARTIALLY_RECEIVED,
        approved_amount=D("10000"),
        received_amount=D("12000"),
        approval_evidence_id="approval",
        receipt_evidence_id="receipt",
    )
    with pytest.raises(ValueError):
        incentive.validate()


def test_duplicate_incentive_cannot_be_double_counted():
    incentive = Incentive(
        incentive_id="same",
        program="Program",
        status=IncentiveStatus.RECEIVED,
        approved_amount=D("10000"),
        received_amount=D("10000"),
        approval_evidence_id="approval",
        receipt_evidence_id="receipt",
    )
    with pytest.raises(ValueError):
        total_captured_value([incentive, incentive])


def test_expired_credit_cannot_carry_received_value():
    incentive = Incentive(
        incentive_id="expired",
        program="Program",
        status=IncentiveStatus.EXPIRED,
        approved_amount=D("10000"),
        received_amount=D("5000"),
    )
    with pytest.raises(ValueError):
        incentive.validate()
