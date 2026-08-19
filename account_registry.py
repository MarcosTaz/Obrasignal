"""Account/tenant registry and subscription state."""

from datetime import datetime, timedelta, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'active',
    plan TEXT NOT NULL DEFAULT 'pilot',
    created_at TEXT NOT NULL,
    trial_ends_at TEXT,
    entitlement_expires_at TEXT,
    store TEXT,
    product_id TEXT,
    original_transaction_id TEXT,
    subscription_status TEXT NOT NULL DEFAULT 'trial'
)
"""


def ensure_account_table(conn):
    conn.execute(SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()}
    migrations = {
        "trial_ends_at": "ALTER TABLE accounts ADD COLUMN trial_ends_at TEXT",
        "entitlement_expires_at": "ALTER TABLE accounts ADD COLUMN entitlement_expires_at TEXT",
        "store": "ALTER TABLE accounts ADD COLUMN store TEXT",
        "product_id": "ALTER TABLE accounts ADD COLUMN product_id TEXT",
        "original_transaction_id": "ALTER TABLE accounts ADD COLUMN original_transaction_id TEXT",
        "subscription_status": "ALTER TABLE accounts ADD COLUMN subscription_status TEXT NOT NULL DEFAULT 'trial'",
    }
    for name, statement in migrations.items():
        if name not in columns:
            conn.execute(statement)
    conn.commit()


def ensure_account(conn, account_id, status='active', plan='pilot'):
    ensure_account_table(conn)
    account_id = str(account_id)
    now = datetime.now(timezone.utc)
    existing = conn.execute("SELECT account_id FROM accounts WHERE account_id=?", (account_id,)).fetchone()
    if existing:
        conn.execute("UPDATE accounts SET status=? WHERE account_id=?", (status, account_id))
    else:
        trial_ends_at = (now + timedelta(days=14)).isoformat()
        conn.execute(
            """INSERT INTO accounts(account_id, status, plan, created_at, trial_ends_at, subscription_status)
               VALUES(?, ?, ?, ?, ?, 'trial')""",
            (account_id, status, plan, now.isoformat(), trial_ends_at),
        )
    conn.commit()


def get_account(conn, account_id):
    ensure_account_table(conn)
    row = conn.execute("SELECT * FROM accounts WHERE account_id=?", (str(account_id),)).fetchone()
    return dict(row) if row else None


def update_subscription(conn, account_id, *, plan, subscription_status,
                        entitlement_expires_at=None, store=None, product_id=None,
                        original_transaction_id=None):
    ensure_account_table(conn)
    conn.execute(
        """UPDATE accounts SET plan=?, subscription_status=?, entitlement_expires_at=?,
           store=COALESCE(?, store), product_id=COALESCE(?, product_id),
           original_transaction_id=COALESCE(?, original_transaction_id)
           WHERE account_id=?""",
        (plan, subscription_status, entitlement_expires_at, store, product_id,
         original_transaction_id, str(account_id)),
    )
    conn.commit()


def subscription_state(account):
    if not account:
        return {"plan": "none", "active": False, "source": None, "expires_at": None}
    now = datetime.now(timezone.utc)
    if account.get("plan") == "pro" and account.get("subscription_status") in {
        "active", "trial", "grace_period", "paused"
    }:
        expires = account.get("entitlement_expires_at")
        if not expires or _parse_iso(expires) > now:
            return {"plan": "pro", "active": True, "source": account.get("store"), "expires_at": expires}
    if account.get("plan") == "pilot":
        expires = account.get("trial_ends_at")
        if expires and _parse_iso(expires) > now:
            return {"plan": "pilot", "active": True, "source": "trial", "expires_at": expires}
    return {"plan": "expired", "active": False, "source": account.get("store"), "expires_at": account.get("entitlement_expires_at") or account.get("trial_ends_at")}


def _parse_iso(value):
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def list_active_accounts(conn):
    ensure_account_table(conn)
    rows = conn.execute("SELECT account_id FROM accounts WHERE status='active' ORDER BY account_id").fetchall()
    return [row[0] for row in rows]
