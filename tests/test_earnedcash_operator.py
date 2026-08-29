from earnedcash.operator import AssistedPilotOperator
from earnedcash.service import PayloadError
from earnedcash.store import EarnedCashStore

import pytest


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


def verified_chain(*, due=True, project_id="p1"):
    return [
        {"record_id":"a1","customer_id":"c1","project_id":project_id,"currency":"GBP","kind":"APPLICATION","amount":"100","verified":True},
        {"record_id":"c1x","customer_id":"c1","project_id":project_id,"currency":"GBP","kind":"CERTIFICATE","amount":"100","relates_to":"a1","verified":True},
        {"record_id":"i1","customer_id":"c1","project_id":project_id,"currency":"GBP","kind":"INVOICE","amount":"100","relates_to":"c1x","verified":True,"due":due},
    ]


def test_operator_verified_project_persists_safe_recovery_queue():
    store = seeded_store()
    operator = AssistedPilotOperator(store)
    result = operator.reconcile_project(
        tenant_id="t1", project_id="p1", rows=verified_chain(due=True)
    )
    assert result["truth_source"] == "ASSISTED_OPERATOR_VERIFIED"
    assert result["due_unpaid"] == "100"
    assert result["queue_persisted"] is True
    cases = store.list_cases(tenant_id="t1", project_id="p1")
    assert len(cases) == 1
    assert cases[0]["case_id"] == "invoice:i1"


def test_operator_zero_recovery_persists_empty_queue():
    store = seeded_store()
    operator = AssistedPilotOperator(store)
    result = operator.reconcile_project(
        tenant_id="t1", project_id="p1", rows=verified_chain(due=False)
    )
    assert result["due_unpaid"] == "0"
    assert result["not_yet_due"] == "100"
    assert result["recovery_queue"] == []
    assert store.list_cases(tenant_id="t1", project_id="p1") == []


def test_operator_rejects_cross_project_payload_before_reconciliation():
    store = seeded_store()
    operator = AssistedPilotOperator(store)
    rows = verified_chain(project_id="p1")
    rows[2]["project_id"] = "other"
    with pytest.raises(PayloadError, match="operator_project_scope_mismatch"):
        operator.reconcile_project(tenant_id="t1", project_id="p1", rows=rows)
    assert store.list_cases(tenant_id="t1", project_id="p1") == []


def test_operator_cannot_write_queue_into_other_tenant_project():
    store = seeded_store()
    operator = AssistedPilotOperator(store)
    with pytest.raises(ValueError, match="project_not_found_for_tenant"):
        operator.reconcile_project(
            tenant_id="t2", project_id="p1", rows=verified_chain(due=True)
        )
