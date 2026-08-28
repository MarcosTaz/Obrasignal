import pytest

from earnedcash.service import PayloadError, reconcile_payload


def chain():
    return [
        {"record_id":"a1","customer_id":"c1","project_id":"p1","currency":"GBP","kind":"APPLICATION","amount":"100","verified":True},
        {"record_id":"c1","customer_id":"c1","project_id":"p1","currency":"GBP","kind":"CERTIFICATE","amount":"100","relates_to":"a1","verified":True},
        {"record_id":"i1","customer_id":"c1","project_id":"p1","currency":"GBP","kind":"INVOICE","amount":"100","relates_to":"c1","verified":True,"due":True},
    ]


def test_service_injects_tenant_and_returns_due_unpaid():
    result = reconcile_payload(chain(), tenant_id="tenant-test")
    assert result["tenant_id"] == "tenant-test"
    assert result["due_unpaid"] == "100"
    assert result["verified_cash"] == "0"


def test_payload_cannot_override_tenant():
    rows = chain(); rows[0]["tenant_id"] = "other"
    with pytest.raises(PayloadError, match="tenant_id_is_server_controlled"):
        reconcile_payload(rows, tenant_id="tenant-test")


def test_invalid_kind_is_explicit_error():
    rows = chain(); rows[1]["kind"] = "NOT_A_KIND"
    with pytest.raises(PayloadError, match="invalid kind"):
        reconcile_payload(rows, tenant_id="tenant-test")


def test_invalid_amount_is_not_coerced_to_zero():
    rows = chain(); rows[2]["amount"] = "NaN"
    with pytest.raises(PayloadError, match="invalid amount"):
        reconcile_payload(rows, tenant_id="tenant-test")


def test_unverified_chain_fails_closed():
    rows = chain(); rows[0]["verified"] = False
    result = reconcile_payload(rows, tenant_id="tenant-test")
    assert result["due_unpaid"] == "0"
    assert result["unknown_value"] == "100"


def test_records_must_be_array():
    with pytest.raises(PayloadError, match="records_array_required"):
        reconcile_payload({}, tenant_id="tenant-test")
