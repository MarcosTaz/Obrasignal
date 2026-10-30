"""SQLite concurrency interleavings: deletion and delayed billing updates.

An IMMEDIATE deletion transaction owns the database write lock while a separate
connection tries to publish a paid entitlement. After COMMIT, the conditional
update must lose; after ROLLBACK, normal payments must still work.
"""
from datetime import datetime, timedelta, timezone
import sqlite3
import threading
import time

import pytest

from account_registry import (
    ACCOUNT_DELETION_LOCKED_STATUSES,
    ensure_account, get_account, subscription_state, update_subscription,
)


@pytest.mark.parametrize("deletion_status", sorted(ACCOUNT_DELETION_LOCKED_STATUSES))
@pytest.mark.parametrize("deletion_commits", [False, True])
def test_deletion_vs_payment_serialization(tmp_path, deletion_status, deletion_commits):
    database = str(tmp_path / "deletion-payment-race.db")

    def connect():
        c = sqlite3.connect(database, timeout=5.0)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=5000")
        return c

    keeper = connect()
    keeper.execute("PRAGMA journal_mode=WAL")
    ensure_account(keeper, "tenant-a")
    ensure_account(keeper, "tenant-b")
    keeper.execute(
        "UPDATE accounts SET plan='expired', subscription_status='none' "
        "WHERE account_id='tenant-a'"
    )
    keeper.commit()

    # The deletion decision is held uncommitted while a separate connection
    # attempts the billing update; SQLite must serialize the two writes.
    keeper.execute("BEGIN IMMEDIATE")
    keeper.execute(
        "UPDATE accounts SET status=? WHERE account_id='tenant-a'",
        (deletion_status,),
    )

    launched = threading.Event()
    outcomes = []
    def payment_worker():
        c = connect()
        try:
            launched.set()
            changed = update_subscription(
                c, "tenant-a", plan="pro", subscription_status="active",
                entitlement_expires_at=(
                    datetime.now(timezone.utc) + timedelta(days=7)
                ).isoformat(),
            )
            outcomes.append(("ok", changed))
        except Exception as exc:
            outcomes.append(("error", repr(exc)))
        finally:
            c.close()

    thread = threading.Thread(target=payment_worker, daemon=True)
    thread.start()
    assert launched.wait(2)
    time.sleep(0.03)

    if deletion_commits:
        keeper.commit()
    else:
        keeper.rollback()
    thread.join(timeout=6)
    assert not thread.is_alive(), "SQLite billing writer failed to terminate"
    assert len(outcomes) == 1, outcomes
    assert outcomes[0][0] == "ok", outcomes

    account = get_account(keeper, "tenant-a")
    if deletion_commits:
        assert outcomes[0][1] is False
        assert account["status"] == deletion_status
        assert account["plan"] == "expired"
        assert account["subscription_status"] == "none"
        assert subscription_state(account)["active"] is False
    else:
        assert outcomes[0][1] is True
        assert account["status"] == "active"
        assert account["plan"] == "pro"
        assert subscription_state(account)["active"] is True

    # The other account is never modified by a shared-database race.
    other = get_account(keeper, "tenant-b")
    assert other["status"] == "active"
    assert other["plan"] == "evaluation"
    keeper.close()
