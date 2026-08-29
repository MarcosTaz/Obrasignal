from decimal import Decimal, getcontext

import pytest

from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.state import AssistedCaseState
from factories.capacity_commitment.synthetic_cases import case
from factories.capacity_commitment.workflow import (
    Engagement,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowRepository,
)


def save_case(repo, *, tenant="tenant-a", case_id="case-1", company="supplier-1", customer="oem-1", program="program-1", currency="EUR"):
    state = AssistedCaseState(
        tenant_id=tenant,
        company_id=company,
        customer_id=customer,
        program_id=program,
        recovery_case=case(case_id, currency=currency),
        evidence_refs=("contract:1",),
        contract_id="lta-1",
        deadline="2099-09-30",
    )
    repo.save(state)
    return state


def engagement(**overrides):
    values = dict(
        tenant_id="tenant-a",
        engagement_id="eng-1",
        company_id="supplier-1",
        customer_id="oem-1",
        program_id="program-1",
        currency="EUR",
    )
    values.update(overrides)
    return Engagement(**values)


def event(event_id, event_type, *, case_id="case-1", amount=None, currency=None, tenant="tenant-a", engagement_id="eng-1"):
    return WorkflowEvent(
        tenant_id=tenant,
        event_id=event_id,
        engagement_id=engagement_id,
        event_type=event_type,
        occurred_at="2026-08-29T20:00:00Z",
        case_id=case_id,
        amount=amount,
        currency=currency,
        external_ref="buyer-thread:1",
        note="synthetic workflow evidence",
    )


def test_engagement_is_create_only_idempotent_and_tenant_scoped(tmp_path):
    repo = WorkflowRepository(str(tmp_path / "capacity.db"))
    item = engagement()
    assert repo.save_engagement(item) is True
    assert repo.save_engagement(item) is False
    assert repo.load_engagement(tenant_id="tenant-a", engagement_id="eng-1") == item
    with pytest.raises(KeyError):
        repo.load_engagement(tenant_id="tenant-b", engagement_id="eng-1")
    with pytest.raises(FileExistsError, match="different scope"):
        repo.save_engagement(engagement(program_id="other"))


def test_case_link_requires_same_tenant_and_exact_engagement_identity(tmp_path):
    db = tmp_path / "capacity.db"
    cases = CapacityRepository(str(db))
    workflow = WorkflowRepository(str(db))
    workflow.save_engagement(engagement())
    save_case(cases)

    assert workflow.append_event(event("link", WorkflowEventType.CASE_LINKED)) is True

    save_case(cases, case_id="wrong-company", company="supplier-2")
    with pytest.raises(ValueError, match="company_id"):
        workflow.append_event(event("bad-company", WorkflowEventType.CASE_LINKED, case_id="wrong-company"))

    save_case(cases, tenant="tenant-b", case_id="foreign")
    with pytest.raises(KeyError, match="case not found"):
        workflow.append_event(event("foreign", WorkflowEventType.CASE_LINKED, case_id="foreign"))


def test_action_and_outcome_events_are_append_only_and_exact_retry_idempotent(tmp_path):
    db = tmp_path / "capacity.db"
    cases = CapacityRepository(str(db))
    workflow = WorkflowRepository(str(db))
    workflow.save_engagement(engagement())
    save_case(cases)

    submitted = event("submit", WorkflowEventType.ACTION_SUBMITTED)
    assert workflow.append_event(submitted) is True
    assert workflow.append_event(submitted) is False
    with pytest.raises(FileExistsError, match="different content"):
        workflow.append_event(
            WorkflowEvent(
                **{**submitted.__dict__, "note": "changed note"}
            )
        )


def test_customer_recovery_and_our_revenue_are_never_conflated(tmp_path):
    db = tmp_path / "capacity.db"
    cases = CapacityRepository(str(db))
    workflow = WorkflowRepository(str(db))
    workflow.save_engagement(engagement())
    save_case(cases)

    workflow.append_event(event("submitted", WorkflowEventType.ACTION_SUBMITTED))
    workflow.append_event(
        event(
            "customer-cash",
            WorkflowEventType.CUSTOMER_RECOVERY_RECEIVED,
            amount=Decimal("125000.50"),
            currency="EUR",
        )
    )
    workflow.append_event(
        event(
            "invoice",
            WorkflowEventType.OUR_INVOICE_ISSUED,
            case_id=None,
            amount=Decimal("3500"),
            currency="EUR",
        )
    )
    workflow.append_event(
        event(
            "our-cash",
            WorkflowEventType.OUR_PAYMENT_RECEIVED,
            case_id=None,
            amount=Decimal("3500"),
            currency="EUR",
        )
    )

    summary = workflow.summary(tenant_id="tenant-a", engagement_id="eng-1")
    assert summary.customer_recovery_received == Decimal("125000.50")
    assert summary.our_invoice_issued == Decimal("3500")
    assert summary.our_payment_received == Decimal("3500")
    assert summary.action_submitted is True


def test_money_event_requires_exact_decimal_and_engagement_currency(tmp_path):
    db = tmp_path / "capacity.db"
    CapacityRepository(str(db))
    workflow = WorkflowRepository(str(db))
    workflow.save_engagement(engagement())

    with pytest.raises(ValueError, match="requires amount and currency"):
        workflow.append_event(
            event("missing-money", WorkflowEventType.OUR_PAYMENT_RECEIVED, case_id=None)
        )
    with pytest.raises(ValueError, match="does not match engagement"):
        workflow.append_event(
            event(
                "wrong-currency",
                WorkflowEventType.OUR_PAYMENT_RECEIVED,
                case_id=None,
                amount=Decimal("100"),
                currency="GBP",
            )
        )
    with pytest.raises(ValueError, match="finite non-negative Decimal"):
        workflow.append_event(
            event(
                "float-money",
                WorkflowEventType.OUR_PAYMENT_RECEIVED,
                case_id=None,
                amount=100.0,
                currency="EUR",
            )
        )


def test_non_money_event_cannot_smuggle_amount(tmp_path):
    db = tmp_path / "capacity.db"
    cases = CapacityRepository(str(db))
    workflow = WorkflowRepository(str(db))
    workflow.save_engagement(engagement())
    save_case(cases)
    with pytest.raises(ValueError, match="must not carry amount"):
        workflow.append_event(
            event(
                "fake-recovery",
                WorkflowEventType.CUSTOMER_ACCEPTED,
                amount=Decimal("999999"),
                currency="EUR",
            )
        )


def test_case_required_event_cannot_exist_without_case(tmp_path):
    db = tmp_path / "capacity.db"
    CapacityRepository(str(db))
    workflow = WorkflowRepository(str(db))
    workflow.save_engagement(engagement())
    with pytest.raises(ValueError, match="requires case_id"):
        workflow.append_event(
            event("monitor", WorkflowEventType.MONITORING_CHECK, case_id=None)
        )


def test_zero_outcome_is_distinct_valid_outcome_without_fake_recovery(tmp_path):
    db = tmp_path / "capacity.db"
    cases = CapacityRepository(str(db))
    workflow = WorkflowRepository(str(db))
    workflow.save_engagement(engagement())
    save_case(cases)
    workflow.append_event(event("zero", WorkflowEventType.OUTCOME_ZERO_CONFIRMED))
    summary = workflow.summary(tenant_id="tenant-a", engagement_id="eng-1")
    assert summary.zero_outcome_confirmed is True
    assert summary.customer_recovery_received == Decimal("0")
    assert summary.our_payment_received == Decimal("0")


def test_summary_money_isolated_from_global_decimal_context(tmp_path):
    db = tmp_path / "capacity.db"
    CapacityRepository(str(db))
    workflow = WorkflowRepository(str(db))
    workflow.save_engagement(engagement())
    workflow.append_event(
        event(
            "invoice-a",
            WorkflowEventType.OUR_INVOICE_ISSUED,
            case_id=None,
            amount=Decimal("12345678901234567890.25"),
            currency="EUR",
        )
    )
    workflow.append_event(
        event(
            "invoice-b",
            WorkflowEventType.OUR_INVOICE_ISSUED,
            case_id=None,
            amount=Decimal("0.75"),
            currency="EUR",
        )
    )
    old = getcontext().prec
    try:
        getcontext().prec = 6
        summary = workflow.summary(tenant_id="tenant-a", engagement_id="eng-1")
    finally:
        getcontext().prec = old
    assert summary.our_invoice_issued == Decimal("12345678901234567891.00")


def test_workflow_events_are_tenant_isolated(tmp_path):
    db = tmp_path / "capacity.db"
    cases = CapacityRepository(str(db))
    workflow = WorkflowRepository(str(db))
    workflow.save_engagement(engagement())
    workflow.save_engagement(engagement(tenant_id="tenant-b"))
    save_case(cases)
    save_case(cases, tenant="tenant-b")
    workflow.append_event(event("a", WorkflowEventType.CASE_LINKED))
    workflow.append_event(event("b", WorkflowEventType.CASE_LINKED, tenant="tenant-b"))
    assert [item.event_id for item in workflow.list_events(tenant_id="tenant-a", engagement_id="eng-1")] == ["a"]
    assert [item.event_id for item in workflow.list_events(tenant_id="tenant-b", engagement_id="eng-1")] == ["b"]
