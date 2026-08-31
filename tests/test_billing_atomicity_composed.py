"""Billing composition acceptance for projection/event acknowledgement atomicity."""
from datetime import datetime, timezone
import sqlite3

import pytest

import account_registry as billing


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    billing.ensure_account_table(conn)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS billing_webhook_events(event_id TEXT PRIMARY KEY, received_at TEXT NOT NULL)"
    )
    conn.commit()
    return conn


def test_billing_projection_and_webhook_ack_cannot_split_on_ledger_failure_composed():
    conn = _db()
    billing.ensure_account(conn, "acct-a")
    before = billing.get_account(conn, "acct-a")
    event = {
        "id": "evt-current-ambiguous",
        "type": "RENEWAL",
        "app_user_id": "acct-a",
        "transaction_id": "tx-current-ambiguous",
        "original_transaction_id": "tx-current-ambiguous",
        "product_id": "obrasignal_pro_monthly",
        "entitlement_ids": [billing.PRO_ENTITLEMENT],
        "event_timestamp_ms": 2_000_000_000_000,
        "expiration_at_ms": 2_000_086_400_000,
        "purchased_at_ms": 1_999_900_000_000,
        "store": "play_store",
    }

    conn.execute(
        "CREATE TRIGGER fail_billing_ledger BEFORE INSERT ON billing_webhook_events "
        "BEGIN SELECT RAISE(ABORT, 'controlled ledger failure'); END"
    )
    try:
        billing._sync_account_from_webhook(conn, event)
        with pytest.raises(sqlite3.IntegrityError, match="controlled ledger failure"):
            conn.execute(
                "INSERT INTO billing_webhook_events(event_id, received_at) VALUES(?, ?)",
                (event["id"], datetime.now(timezone.utc).isoformat()),
            )
        conn.rollback()
    finally:
        conn.execute("DROP TRIGGER fail_billing_ledger")

    after = billing.get_account(conn, "acct-a")
    acknowledged = conn.execute(
        "SELECT 1 FROM billing_webhook_events WHERE event_id=?", (event["id"],)
    ).fetchone()

    assert acknowledged is None
    assert after == before
    conn.close()
