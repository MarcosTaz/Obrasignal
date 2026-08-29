from datetime import date, timedelta
from decimal import Decimal

from earnedcash.due_date import DueDateEvidence
from earnedcash.ledger import LedgerKind
from earnedcash.operator import AssistedPilotOperator
from earnedcash.store import EarnedCashStore
from earnedcash.synthetic import diversified_companies


AS_OF = date(2026, 8, 29)


def store_for(*, tenant_id, customer_id, project_id, currency):
    store = EarnedCashStore.memory()
    store.create_company(tenant_id=tenant_id, company_id="company", name="Synthetic Company")
    store.create_customer(
        tenant_id=tenant_id,
        customer_id=customer_id,
        company_id="company",
        name="Synthetic Customer",
    )
    store.create_project(
        tenant_id=tenant_id,
        project_id=project_id,
        company_id="company",
        customer_id=customer_id,
        name="Synthetic Project",
        currency=currency,
    )
    return store


def operator_rows_and_due_evidence(company):
    rows = []
    due_evidence = {}
    for record in company.records:
        # A PAYMENT is an observed ledger fact here, not verified cash. Exact
        # cash verification happens only through CashEvidence after recovery.
        verified = False if record.kind == LedgerKind.PAYMENT else record.verified
        rows.append(
            {
                "record_id": record.record_id,
                "customer_id": record.customer_id,
                "project_id": record.project_id,
                "currency": record.currency,
                "kind": record.kind.value,
                "amount": str(record.amount),
                "relates_to": record.relates_to,
                "verified": verified,
            }
        )
        if record.kind == LedgerKind.INVOICE and record.due is not None:
            due_evidence[record.record_id] = DueDateEvidence(
                due_date=AS_OF if record.due else AS_OF + timedelta(days=1),
                evidence_ref=f"oracle:{record.record_id}:due-date",
                independently_verified=True,
            )
    return rows, due_evidence


def test_five_diversified_companies_match_exposure_oracle_through_assisted_operator():
    companies = diversified_companies()[:5]
    assert len(companies) == 5

    for company in companies:
        first = company.records[0]
        tenant_id = f"pilot-{company.name.lower().replace(' ', '-')}"
        store = store_for(
            tenant_id=tenant_id,
            customer_id=first.customer_id,
            project_id=first.project_id,
            currency=first.currency,
        )
        rows, due_evidence = operator_rows_and_due_evidence(company)
        result = AssistedPilotOperator(store).reconcile_project(
            tenant_id=tenant_id,
            project_id=first.project_id,
            rows=rows,
            as_of=AS_OF,
            due_evidence_by_record=due_evidence,
        )

        # Product-path cash remains zero until exact-scope CashEvidence is recorded.
        assert Decimal(result["verified_cash"]) == Decimal("0"), company.name
        assert store.verified_cash_total(
            tenant_id=tenant_id, project_id=first.project_id
        ) == Decimal("0"), company.name
        assert Decimal(result["due_unpaid"]) == company.oracle_due_unpaid, company.name
        assert Decimal(result["not_yet_due"]) == company.oracle_not_yet_due, company.name
        assert Decimal(result["unknown_value"]) == company.oracle_unknown, company.name
        assert result["p0_count"] == company.oracle_p0, company.name
        assert store.audit_valid(tenant_id) is True, company.name

        expected_queue = company.oracle_due_unpaid > Decimal("0")
        assert bool(store.list_cases(tenant_id=tenant_id, project_id=first.project_id)) is expected_queue


def test_unknown_due_date_company_stays_unknown_without_due_evidence():
    company = next(c for c in diversified_companies() if c.name == "TITAN MEP")
    first = company.records[0]
    store = store_for(
        tenant_id="titan-pilot",
        customer_id=first.customer_id,
        project_id=first.project_id,
        currency=first.currency,
    )
    rows, due_evidence = operator_rows_and_due_evidence(company)
    assert due_evidence == {}
    result = AssistedPilotOperator(store).reconcile_project(
        tenant_id="titan-pilot",
        project_id=first.project_id,
        rows=rows,
        as_of=AS_OF,
        due_evidence_by_record=due_evidence,
    )
    assert result["due_truth"]["titan1-inv"]["state"] == "UNKNOWN"
    assert Decimal(result["verified_cash"]) == Decimal("0")
    assert Decimal(result["unknown_value"]) == Decimal("120000")
    assert result["recovery_queue"] == []
