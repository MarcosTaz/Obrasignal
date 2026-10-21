from datetime import date

import pytest

from earnedcash.due_date import DueDateEvidence
from earnedcash.operator import AssistedPilotOperator
from earnedcash.service import PayloadError
from earnedcash.store import EarnedCashStore


AS_OF = date(2026, 8, 29)


def seeded_store():
    store = EarnedCashStore.memory()
    store.create_company(tenant_id="t1", company_id="co1", name="Alpha Electrical")
    store.create_customer(
        tenant_id="t1", customer_id="c1", company_id="co1", name="Main Contractor"
    )
    store.create_project(
        tenant_id="t1", project_id="p1", company_id="co1", customer_id="c1",
        name="Hospital", currency="GBP"
    )
    return store


def verified_chain(*, project_id="p1", include_due=False):
    invoice = {"record_id":"i1","customer_id":"c1","project_id":project_id,"currency":"GBP","kind":"INVOICE","amount":"100","relates_to":"c1x","verified":True}
    if include_due:
        invoice["due"] = True
    return [
        {"record_id":"a1","customer_id":"c1","project_id":project_id,"currency":"GBP","kind":"APPLICATION","amount":"100","verified":True},
        {"record_id":"c1x","customer_id":"c1","project_id":project_id,"currency":"GBP","kind":"CERTIFICATE","amount":"100","relates_to":"a1","verified":True},
        invoice,
    ]


def due_evidence(due_date):
    return {
        "i1": DueDateEvidence(
            due_date=due_date,
            evidence_ref="invoice:i1:due-date",
            independently_verified=True,
        )
    }


def test_operator_verified_project_persists_safe_recovery_queue_on_due_date():
    store = seeded_store()
    operator = AssistedPilotOperator(store)
    result = operator.reconcile_project(
        tenant_id="t1",
        project_id="p1",
        rows=verified_chain(),
        as_of=AS_OF,
        due_evidence_by_record=due_evidence(AS_OF),
    )
    assert result["truth_source"] == "ASSISTED_OPERATOR_VERIFIED"
    assert result["due_truth"]["i1"]["state"] == "DUE"
    assert result["due_unpaid"] == "100"
    assert result["queue_persisted"] is True
    cases = store.list_cases(tenant_id="t1", project_id="p1")
    assert len(cases) == 1
    assert cases[0]["case_id"] == "invoice:i1"


def test_operator_day_before_due_is_not_yet_due_and_persists_empty_queue():
    store = seeded_store()
    operator = AssistedPilotOperator(store)
    result = operator.reconcile_project(
        tenant_id="t1",
        project_id="p1",
        rows=verified_chain(),
        as_of=AS_OF,
        due_evidence_by_record=due_evidence(date(2026, 8, 30)),
    )
    assert result["due_truth"]["i1"]["state"] == "NOT_YET_DUE"
    assert result["due_unpaid"] == "0"
    assert result["not_yet_due"] == "100"
    assert result["recovery_queue"] == []
    assert store.list_cases(tenant_id="t1", project_id="p1") == []


def test_operator_missing_due_evidence_fails_closed_to_unknown():
    store = seeded_store()
    operator = AssistedPilotOperator(store)
    result = operator.reconcile_project(
        tenant_id="t1", project_id="p1", rows=verified_chain(), as_of=AS_OF
    )
    assert result["due_truth"]["i1"]["state"] == "UNKNOWN"
    assert result["due_unpaid"] == "0"
    assert result["unknown_value"] == "100"
    assert result["recovery_queue"] == []


def test_operator_rejects_magic_due_boolean():
    store = seeded_store()
    operator = AssistedPilotOperator(store)
    with pytest.raises(PayloadError, match="operator_due_boolean_forbidden"):
        operator.reconcile_project(
            tenant_id="t1",
            project_id="p1",
            rows=verified_chain(include_due=True),
            as_of=AS_OF,
            due_evidence_by_record=due_evidence(AS_OF),
        )


def test_operator_rejects_cross_project_payload_before_reconciliation():
    store = seeded_store()
    operator = AssistedPilotOperator(store)
    rows = verified_chain(project_id="p1")
    rows[2]["project_id"] = "other"
    with pytest.raises(PayloadError, match="operator_project_scope_mismatch"):
        operator.reconcile_project(
            tenant_id="t1",
            project_id="p1",
            rows=rows,
            as_of=AS_OF,
            due_evidence_by_record=due_evidence(AS_OF),
        )
    assert store.list_cases(tenant_id="t1", project_id="p1") == []


def test_operator_cannot_write_queue_into_other_tenant_project():
    store = seeded_store()
    operator = AssistedPilotOperator(store)
    with pytest.raises(ValueError, match="project_not_found_for_tenant"):
        operator.reconcile_project(
            tenant_id="t2",
            project_id="p1",
            rows=verified_chain(),
            as_of=AS_OF,
            due_evidence_by_record=due_evidence(AS_OF),
        )
