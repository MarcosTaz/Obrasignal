import pytest

from earnedcash.service import (
    PayloadError,
    reconcile_operator_verified_payload,
    reconcile_payload,
)


def verified_chain(*, currency="GBP", prefix=""):
    return [
        {"record_id":f"{prefix}a1","customer_id":"c1","project_id":"p1","currency":currency,"kind":"APPLICATION","amount":"100","verified":True},
        {"record_id":f"{prefix}c1","customer_id":"c1","project_id":"p1","currency":currency,"kind":"CERTIFICATE","amount":"100","relates_to":f"{prefix}a1","verified":True},
        {"record_id":f"{prefix}i1","customer_id":"c1","project_id":"p1","currency":currency,"kind":"INVOICE","amount":"100","relates_to":f"{prefix}c1","verified":True,"due":True},
    ]


def client_chain(*, currency="GBP", prefix=""):
    rows = verified_chain(currency=currency, prefix=prefix)
    for row in rows:
        row.pop("verified", None)
        row.pop("due", None)
    return rows


def test_operator_verified_service_returns_due_unpaid_and_queue():
    result = reconcile_operator_verified_payload(
        verified_chain(), tenant_id="tenant-test"
    )
    assert result["tenant_id"] == "tenant-test"
    assert result["currency"] == "GBP"
    assert result["due_unpaid"] == "100"
    assert result["verified_cash"] == "0"
    assert result["recovery_queue"][0]["case_id"] == "invoice:i1"
    assert result["recovery_queue"][0]["amount"] == "100"


def test_operator_payment_boolean_cannot_create_verified_cash():
    rows = verified_chain()
    rows.append(
        {"record_id":"pay1","customer_id":"c1","project_id":"p1","currency":"GBP","kind":"PAYMENT","amount":"40","relates_to":"i1","verified":True}
    )
    with pytest.raises(
        PayloadError, match="payment_verified_requires_cash_evidence_boundary"
    ):
        reconcile_operator_verified_payload(rows, tenant_id="tenant-test")


def test_operator_unverified_observed_payment_reduces_open_without_verified_cash():
    rows = verified_chain()
    rows.append(
        {"record_id":"pay1","customer_id":"c1","project_id":"p1","currency":"GBP","kind":"PAYMENT","amount":"40","relates_to":"i1","verified":False}
    )
    result = reconcile_operator_verified_payload(rows, tenant_id="tenant-test")
    assert result["verified_cash"] == "0"
    assert result["due_unpaid"] == "60"
    assert result["positions"][0]["verified_cash"] == "0"


def test_client_cannot_self_attest_verified_truth():
    with pytest.raises(PayloadError, match="verified_is_server_controlled"):
        reconcile_payload(verified_chain(), tenant_id="tenant-test")


def test_client_cannot_self_attest_due_truth():
    rows = client_chain()
    rows[2]["due"] = True
    with pytest.raises(PayloadError, match="due_is_server_controlled"):
        reconcile_payload(rows, tenant_id="tenant-test")


def test_client_payload_without_server_truth_fails_closed_to_unknown():
    result = reconcile_payload(client_chain(), tenant_id="tenant-test")
    assert result["tenant_id"] == "tenant-test"
    assert result["due_unpaid"] == "0"
    assert result["verified_cash"] == "0"
    assert result["unknown_value"] == "100"
    assert result["recovery_queue"] == []


def test_payload_cannot_override_tenant():
    rows = client_chain(); rows[0]["tenant_id"] = "other"
    with pytest.raises(PayloadError, match="tenant_id_is_server_controlled"):
        reconcile_payload(rows, tenant_id="tenant-test")


def test_invalid_kind_is_explicit_error():
    rows = client_chain(); rows[1]["kind"] = "NOT_A_KIND"
    with pytest.raises(PayloadError, match="invalid kind"):
        reconcile_payload(rows, tenant_id="tenant-test")


def test_invalid_amount_is_not_coerced_to_zero():
    rows = client_chain(); rows[2]["amount"] = "NaN"
    with pytest.raises(PayloadError, match="invalid amount"):
        reconcile_payload(rows, tenant_id="tenant-test")


def test_mixed_currency_client_payload_never_returns_cross_currency_total_or_queue():
    rows = client_chain(currency="GBP", prefix="g") + client_chain(currency="EUR", prefix="e")
    result = reconcile_payload(rows, tenant_id="tenant-test")
    assert result["currency"] is None
    assert result["due_unpaid"] == "0"
    assert result["unknown_value"] == "200"
    assert result["recovery_queue"] == []
    assert any(a["code"] == "MULTI_CURRENCY_DATASET" for a in result["anomalies"])


def test_records_must_be_array():
    with pytest.raises(PayloadError, match="records_array_required"):
        reconcile_payload({}, tenant_id="tenant-test")
