import hashlib
import hmac
import json

from factory_cloud.stripe_webhook_http import MAX_WEBHOOK_BYTES, handle_stripe_webhook


def _env():
    return {
        "FACTORY_STRIPE_SECRET_KEY": "sk_test_not_real",
        "FACTORY_STRIPE_WEBHOOK_SECRET": "whsec_http_test",
        "FACTORY_STRIPE_LIVEMODE": "false",
    }


def _payload():
    event = {
        "id": "evt_http_1",
        "type": "customer.updated",
        "livemode": False,
        "data": {"object": {"id": "cus_test", "object": "customer"}},
    }
    return json.dumps(event, separators=(",", ":")).encode("utf-8")


def _signature(body, timestamp=1_800_000_000):
    digest = hmac.new(
        b"whsec_http_test",
        str(timestamp).encode("ascii") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={digest}"


def test_webhook_http_requires_raw_signed_payload(tmp_path):
    status, payload = handle_stripe_webhook(
        b"",
        {},
        environ=_env(),
        ledger_path=tmp_path / "finance.sqlite3",
    )
    assert status == 400
    assert payload["error"] == "empty_body"

    body = _payload()
    status, payload = handle_stripe_webhook(
        body,
        {},
        environ=_env(),
        ledger_path=tmp_path / "finance.sqlite3",
    )
    assert status == 400
    assert payload["error"] == "missing_signature"


def test_webhook_http_rejects_oversized_payload_before_provider_processing(tmp_path):
    status, payload = handle_stripe_webhook(
        b"x" * (MAX_WEBHOOK_BYTES + 1),
        {"Stripe-Signature": "t=1,v1=bad"},
        environ=_env(),
        ledger_path=tmp_path / "finance.sqlite3",
    )
    assert status == 413
    assert payload["error"] == "payload_too_large"


def test_webhook_http_accepts_verified_event_and_is_idempotent(tmp_path):
    body = _payload()
    headers = {"Stripe-Signature": _signature(body)}
    ledger_path = tmp_path / "finance.sqlite3"

    status, result = handle_stripe_webhook(
        body,
        headers,
        environ=_env(),
        ledger_path=ledger_path,
        now=1_800_000_000,
    )
    assert status == 200
    assert result == {
        "accepted": True,
        "duplicate": False,
        "state_changed": False,
        "type": "customer.updated",
    }

    status, duplicate = handle_stripe_webhook(
        body,
        headers,
        environ=_env(),
        ledger_path=ledger_path,
        now=1_800_000_000,
    )
    assert status == 200
    assert duplicate["duplicate"] is True
    assert duplicate["state_changed"] is False


def test_webhook_http_wrong_signature_fails_without_leaking_details(tmp_path):
    body = _payload()
    status, result = handle_stripe_webhook(
        body,
        {"stripe-signature": "t=1800000000,v1=wrong"},
        environ=_env(),
        ledger_path=tmp_path / "finance.sqlite3",
        now=1_800_000_000,
    )
    assert status == 400
    assert result == {"accepted": False, "error": "invalid_provider_evidence"}
