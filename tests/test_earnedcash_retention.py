from decimal import Decimal

from earnedcash.retention import RetentionInput, RetentionState, evaluate_retention


def item(**kwargs):
    base = dict(
        tenant_id="t1",
        project_id="p1",
        currency="GBP",
        amount_withheld=Decimal("10000"),
    )
    base.update(kwargs)
    return RetentionInput(**base)


def test_retention_not_due_is_zero_recovery():
    result = evaluate_retention(item(release_due=False))
    assert result.state == RetentionState.NOT_YET_DUE
    assert result.potentially_recoverable == Decimal("0")


def test_valid_defect_blocks_recovery():
    result = evaluate_retention(
        item(release_due=True, valid_defects_open=True, closeout_complete=True)
    )
    assert result.state == RetentionState.DEFECTS_BLOCKED
    assert result.potentially_recoverable == Decimal("0")


def test_missing_closeout_blocks_recovery():
    result = evaluate_retention(
        item(release_due=True, valid_defects_open=False, closeout_complete=False)
    )
    assert result.state == RetentionState.CLOSEOUT_BLOCKED
    assert result.potentially_recoverable == Decimal("0")


def test_unknown_defect_state_fails_closed():
    result = evaluate_retention(
        item(release_due=True, valid_defects_open=None, closeout_complete=True)
    )
    assert result.state == RetentionState.UNKNOWN
    assert result.potentially_recoverable == Decimal("0")


def test_stated_maturity_without_release_evidence_fails_closed():
    result = evaluate_retention(
        item(release_due=True, valid_defects_open=False, closeout_complete=True)
    )
    assert result.state == RetentionState.UNKNOWN
    assert result.potentially_recoverable == Decimal("0")


def test_evidenced_matured_retention_surfaces_balance():
    result = evaluate_retention(
        item(
            release_due=True,
            valid_defects_open=False,
            closeout_complete=True,
            release_condition_evidence_verified=True,
        )
    )
    assert result.state == RetentionState.MATURED_EVIDENCE_SUPPORTED
    assert result.potentially_recoverable == Decimal("10000")


def test_partial_release_uses_remaining_balance_only():
    result = evaluate_retention(
        item(
            amount_released=Decimal("4000"),
            release_due=True,
            valid_defects_open=False,
            closeout_complete=True,
            release_condition_evidence_verified=True,
            payment_evidence_verified=True,
        )
    )
    assert result.verified_released_cash == Decimal("4000")
    assert result.held_balance == Decimal("6000")
    assert result.potentially_recoverable == Decimal("6000")


def test_release_without_payment_evidence_is_not_verified_cash():
    result = evaluate_retention(
        item(
            amount_released=Decimal("4000"),
            release_due=False,
            payment_evidence_verified=False,
        )
    )
    assert result.verified_released_cash == Decimal("0")


def test_over_release_is_unknown_not_negative_balance():
    result = evaluate_retention(
        item(amount_released=Decimal("11000"), payment_evidence_verified=True)
    )
    assert result.state == RetentionState.UNKNOWN
    assert result.potentially_recoverable == Decimal("0")
