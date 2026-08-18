"""Account/tenant registry used by personalized opportunity evaluation."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'active',
    plan TEXT NOT NULL DEFAULT 'pilot',
    created_at TEXT NOT NULL
)
"""

from datetime import datetime, timezone


def ensure_account_table(conn):
    conn.execute(SCHEMA)
    conn.commit()


def ensure_account(conn, account_id, status='active', plan='pilot'):
    ensure_account_table(conn)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO accounts(account_id, status, plan, created_at)
           VALUES(?, ?, ?, ?)
           ON CONFLICT(account_id) DO UPDATE SET status=excluded.status, plan=excluded.plan""",
        (str(account_id), status, plan, now),
    )
    conn.commit()


def list_active_accounts(conn):
    ensure_account_table(conn)
    rows = conn.execute(
        "SELECT account_id FROM accounts WHERE status='active' ORDER BY account_id"
    ).fetchall()
    return [row[0] for row in rows]
