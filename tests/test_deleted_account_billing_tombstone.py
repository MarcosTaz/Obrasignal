"""Deletion tombstones must survive delayed, authenticated RevenueCat events.

These fixtures use only local SQLite and Flask clients; no remote identity,
billing provider, live customers, or production resources are contacted.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import time

import pytest

import app
import api
from account_registry import (
    _sync_account_from_webhook, ensure_account, get_account,
    subscription_state, update_subscription,
)


LOCKED = (
    "deletion_pending",
    "deletion_failed",
    "deleted_pending_revocation",
    "deleted",
)


def _tombstone(conn, account_id, status):
    ensure_account(conn, account_id)
    conn.execute(
        "UPDATE accounts SET status=?, plan='expired', subscription_status='none' WHERE account_id=?",
        (status, account_id),
    )
    conn.commit()


@pytest.mark.parametrize("status", LOCKED)
def test_deletion_state_overrides_any_leftover_paid_entitlement(status):
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_account(conn, "deleted-account")
    conn.execute(
        """UPDATE accounts SET status=?, plan='pro',
           subscription_status='active', entitlement_expires_at=?
           WHERE account_id='deleted-account'""",
        (status, (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()),
    )
    conn.commit()
    assert subscription_state(get_account(conn, "deleted-account"))["active"] is False
    conn.close()


@pytest.mark.parametrize("status", LOCKED)
def test_late_revenuecat_webhook_never_reactivates_deleted_account(status):
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _tombstone(conn, "deleted-account", status)
    _sync_account_from_webhook(conn, {
        "id": "late-paid-event",
        "app_user_id": "deleted-account",
        "type": "RENEWAL",
        "expiration_at_ms": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000),
        "store": "app_store",
        "product_id": "obrasignal_pro_monthly",
    })
    row = get_account(conn, "deleted-account")
    assert row["status"] == status
    assert row["plan"] == "expired"
    assert row["subscription_status"] == "none"
    assert row["entitlement_expires_at"] is None
    conn.close()


def test_direct_billing_reconciliation_cannot_overwrite_tombstone():
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _tombstone(conn, "deleted-account", "deleted_pending_revocation")
    update_subscription(
        conn, "deleted-account", plan="pro", subscription_status="active",
        entitlement_expires_at=(datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
    )
    row = get_account(conn, "deleted-account")
    assert row["plan"] == "expired"
    assert row["subscription_status"] == "none"
    assert row["entitlement_expires_at"] is None
    conn.close()


def test_tombstoned_account_cannot_recreate_profile_over_http(tmp_path, monkeypatch):
    path = str(tmp_path / "tombstone-http.db")
    monkeypatch.setattr(app, "DB", path)
    monkeypatch.setenv("OBRASIGNAL_DB", path)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "deleted-account")
    app.init_db()
    conn = app.db()
    _tombstone(conn, "deleted-account", "deleted_pending_revocation")
    conn.close()
    client = api.APP.test_client()
    for method, endpoint, kwargs in (
        (client.get, "/api/v1/profile", {}),
        (client.post, "/api/v1/profile", {"json": {"name": "Resurrected"}}),
        (client.get, "/api/v1/sources", {}),
    ):
        response = method(endpoint, **kwargs)
        # The existing global privacy guard correctly returns 423 Locked.
        assert response.status_code == 423, (endpoint, response.status_code, response.get_json())
        assert response.get_json()["error"] == "account_private_data_locked"
    conn = app.db()
    assert get_account(conn, "deleted-account")["status"] == "deleted_pending_revocation"
    conn.close()


def test_signed_webhook_acknowledged_without_reviving_deleted_customer(tmp_path, monkeypatch):
    path = str(tmp_path / "tombstone-webhook.db")
    monkeypatch.setattr(app, "DB", path)
    monkeypatch.setenv("OBRASIGNAL_DB", path)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    secret = "local-test-only-hmac-key"
    monkeypatch.setenv("REVENUECAT_WEBHOOK_SECRET", secret)
    app.init_db()
    conn = app.db()
    _tombstone(conn, "deleted-account", "deleted_pending_revocation")
    conn.close()
    payload = {"event": {
        "id": "late-event-immutable-001", "app_user_id": "deleted-account",
        "type": "RENEWAL", "expiration_at_ms": int(
            (datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000
        ),
    }}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    stamp = str(int(time.time()))
    sig = hmac.new(secret.encode(), stamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    response = api.APP.test_client().post(
        "/api/v1/billing/webhook", data=raw,
        headers={"X-RevenueCat-Webhook-Signature": f"t={stamp},v1={sig}"},
        content_type="application/json",
    )
    assert response.status_code == 200
    conn = app.db()
    row = get_account(conn, "deleted-account")
    assert row["status"] == "deleted_pending_revocation"
    assert row["plan"] == "expired"
    assert conn.execute(
        "SELECT COUNT(*) FROM billing_webhook_events WHERE event_id='late-event-immutable-001'"
    ).fetchone()[0] == 1
    conn.close()
