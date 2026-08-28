from decimal import Decimal

from earnedcash.final_account import FinalAccountInput, FinalAccountState, evaluate_final_account


def item(**kwargs):
    data = dict(
        tenant_id="t1",
        project_id="p1",
        currency="GBP",
        contractor_position=Decimal("120000"),
        customer_position=Decimal("120000"),
        agreed_value=Decimal("120000"),
        invoiced_against_final=Decimal("120000"),
        paid_against_final=Decimal("100000"),
        agreement_evidence_verified=True,
        invoice_evidence_verified=True,
        payment_evidence_verified=True,
        payment_due=True,
    )
    data.update(kwargs)
    return FinalAccountInput(**data)


def test_unagreed_position_is_not_recovery():
    result = evaluate_final_account(
        item(
            agreed_value=None,
            contractor_position=Decimal("120000"),
            customer_position=Decimal("100000"),
            invoiced_against_final=None,
            paid_against_final=None,
            agreement_evidence_verified=False,
        )
    )
    assert result.state == FinalAccountState.DISPUTED
    assert result.potentially_recoverable == Decimal("0")
    assert result.delta_positions == Decimal("20000")


def test_agreed_without_agreement_evidence_is_unknown():
    result = evaluate_final_account(item(agreement_evidence_verified=False))
    assert result.state == FinalAccountState.UNKNOWN
    assert result.potentially_recoverable == Decimal("0")


def test_agreed_not_due_is_zero_recovery():
    result = evaluate_final_account(item(payment_due=False))
    assert result.state == FinalAccountState.AGREED_NOT_DUE
    assert result.potentially_recoverable == Decimal("0")
    assert result.open_balance == Decimal("20000")


def test_agreed_due_unpaid_is_recoverable_with_evidence():
    result = evaluate_final_account(item())
    assert result.state == FinalAccountState.AGREED_DUE_UNPAID
    assert result.potentially_recoverable == Decimal("20000")
    assert result.verified_cash == Decimal("100000")


def test_deductions_and_disputed_value_are_not_claimed():
    result = evaluate_final_account(
        item(valid_deductions=Decimal("5000"), disputed_value=Decimal("3000"))
    )
    assert result.potentially_recoverable == Decimal("12000")
    assert result.disputed_value == Decimal("3000")


def test_invoice_evidence_missing_blocks_recovery():
    result = evaluate_final_account(item(invoice_evidence_verified=False))
    assert result.state == FinalAccountState.UNKNOWN
    assert result.potentially_recoverable == Decimal("0")


def test_unknown_due_date_blocks_recovery():
    result = evaluate_final_account(item(payment_due=None))
    assert result.state == FinalAccountState.UNKNOWN
    assert result.potentially_recoverable == Decimal("0")


def test_payment_without_payment_evidence_is_not_verified_cash():
    result = evaluate_final_account(item(payment_evidence_verified=False))
    assert result.verified_cash == Decimal("0")
    assert result.potentially_recoverable == Decimal("20000")


def test_paid_greater_than_invoiced_fails_closed():
    result = evaluate_final_account(
        item(invoiced_against_final=Decimal("100000"), paid_against_final=Decimal("110000"))
    )
    assert result.state == FinalAccountState.UNKNOWN
    assert result.potentially_recoverable == Decimal("0")
