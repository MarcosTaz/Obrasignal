from decimal import Decimal

import pytest

from earnedcash.models import EvidenceItem, EvidenceKind, ProjectCashInput, TruthState
from earnedcash.oracle import SCENARIOS
from earnedcash.reconciliation import reconcile_project


def evidence(eid, kind):
    return EvidenceItem(evidence_id=eid, kind=kind, verified=True)


def make(**kwargs):
    defaults = dict(
        tenant_id="tenant-a",
        customer_id="customer-a",
        project_id="project-a",
        currency="GBP",
        certified_value=Decimal("100000"),
        invoiced_value=Decimal("100000"),
        paid_value=Decimal("100000"),
    )
    defaults.update(kwargs)
    return ProjectCashInput(**defaults)


def test_zero_recovery_not_yet_due_is_pass():
    truth = SCENARIOS["zero_recovery"]
    result = reconcile_project(
        make(
            invoiced_value=Decimal("125000"),
            certified_value=Decimal("125000"),
            paid_value=Decimal("100000"),
            payment_due=False,
            evidence=(evidence("inv-1", EvidenceKind.INVOICE),),
        )
    )
    assert result.potentially_recoverable == truth.true_recoverable
    assert result.not_yet_due == truth.true_not_yet_due
    assert result.cases == ()


def test_matured_retention_requires_release_evidence():
    result = reconcile_project(
        make(retention_held=Decimal("50000"), retention_matured=True)
    )
    assert result.potentially_recoverable == Decimal("0")
    assert result.unknown is True
    assert result.cases[0].state == TruthState.UNKNOWN


def test_matured_retention_with_evidence_is_supported():
    truth = SCENARIOS["matured_retention"]
    result = reconcile_project(
        make(
            retention_held=Decimal("50000"),
            retention_matured=True,
            evidence=(evidence("ret-release-1", EvidenceKind.RETENTION_RELEASE),),
        )
    )
    assert result.potentially_recoverable == truth.true_recoverable
    assert [c.category for c in result.cases] == list(truth.expected_categories)


def test_certified_not_invoiced_requires_certificate():
    result = reconcile_project(
        make(
            certified_value=Decimal("130000"),
            invoiced_value=Decimal("100000"),
            paid_value=Decimal("100000"),
        )
    )
    assert result.potentially_recoverable == Decimal("0")
    assert result.unknown is True


def test_certified_not_invoiced_with_certificate_is_supported():
    truth = SCENARIOS["certified_not_invoiced"]
    result = reconcile_project(
        make(
            certified_value=Decimal("130000"),
            invoiced_value=Decimal("100000"),
            paid_value=Decimal("100000"),
            evidence=(evidence("cert-1", EvidenceKind.CERTIFICATE),),
        )
    )
    assert result.potentially_recoverable == truth.true_recoverable
    assert [c.category for c in result.cases] == list(truth.expected_categories)


def test_due_unpaid_requires_invoice_evidence():
    result = reconcile_project(
        make(
            certified_value=Decimal("125000"),
            invoiced_value=Decimal("125000"),
            paid_value=Decimal("100000"),
            payment_due=True,
        )
    )
    assert result.potentially_recoverable == Decimal("0")
    assert result.unknown is True


def test_due_unpaid_with_evidence_surfaces_net_of_valid_deductions_and_dispute():
    result = reconcile_project(
        make(
            certified_value=Decimal("140000"),
            invoiced_value=Decimal("140000"),
            paid_value=Decimal("100000"),
            payment_due=True,
            disputed_value=Decimal("5000"),
            valid_deductions=Decimal("7000"),
            evidence=(evidence("inv-1", EvidenceKind.INVOICE),),
        )
    )
    assert result.potentially_recoverable == Decimal("28000")
    assert result.disputed == Decimal("5000")


def test_paid_greater_than_invoiced_fails_closed():
    result = reconcile_project(
        make(
            certified_value=Decimal("100000"),
            invoiced_value=Decimal("90000"),
            paid_value=Decimal("100000"),
        )
    )
    assert result.unknown is True
    assert result.potentially_recoverable == Decimal("0")
    assert result.cases == ()


def test_invoiced_greater_than_certified_fails_closed():
    result = reconcile_project(
        make(
            certified_value=Decimal("90000"),
            invoiced_value=Decimal("100000"),
            paid_value=Decimal("90000"),
        )
    )
    assert result.unknown is True
    assert result.potentially_recoverable == Decimal("0")


def test_negative_values_rejected():
    with pytest.raises(ValueError):
        reconcile_project(make(retention_held=Decimal("-1"), retention_matured=True))


def test_final_account_duplicate_is_not_double_counted():
    result = reconcile_project(
        make(
            certified_value=Decimal("120000"),
            invoiced_value=Decimal("120000"),
            paid_value=Decimal("100000"),
            payment_due=True,
            final_account_agreed_value=Decimal("120000"),
            evidence=(
                evidence("inv-1", EvidenceKind.INVOICE),
                evidence("fa-1", EvidenceKind.FINAL_ACCOUNT),
            ),
        )
    )
    assert result.potentially_recoverable == Decimal("20000")
    assert len(result.cases) == 1


def test_tenant_identity_preserved_in_cases():
    result = reconcile_project(
        make(
            tenant_id="tenant-X",
            retention_held=Decimal("1000"),
            retention_matured=True,
            evidence=(evidence("ret-1", EvidenceKind.RETENTION_RELEASE),),
        )
    )
    assert result.cases[0].tenant_id == "tenant-X"


def test_paid_value_without_payment_evidence_is_not_verified_cash():
    result = reconcile_project(make(paid_value=Decimal("100000")))
    assert result.verified_paid == Decimal("0")
    assert result.unknown is True


def test_paid_value_with_matching_payment_evidence_is_verified_cash():
    result = reconcile_project(
        make(
            paid_value=Decimal("100000"),
            evidence=(
                EvidenceItem(
                    evidence_id="bank-1",
                    kind=EvidenceKind.PAYMENT,
                    amount=Decimal("100000"),
                    verified=True,
                ),
            ),
        )
    )
    assert result.verified_paid == Decimal("100000")


def test_payment_evidence_amount_mismatch_fails_closed_for_verified_cash():
    result = reconcile_project(
        make(
            paid_value=Decimal("100000"),
            evidence=(
                EvidenceItem(
                    evidence_id="bank-1",
                    kind=EvidenceKind.PAYMENT,
                    amount=Decimal("99000"),
                    verified=True,
                ),
            ),
        )
    )
    assert result.verified_paid == Decimal("0")
    assert result.unknown is True
