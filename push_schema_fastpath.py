"""Context-safe steady-state fast path for push schema verification."""
from __future__ import annotations

import sqlite3

_REQUIRED_INDEX = "idx_push_devices_account"


def schema_ready(conn) -> bool:
    try:
        conn.execute(
            "SELECT token,account_id,platform,timezone,enabled,created_at,last_seen_at "
            "FROM push_devices LIMIT 0"
        )
        conn.execute(
            "SELECT account_id,enabled,timezone,local_hour,local_minute,updated_at "
            "FROM push_preferences LIMIT 0"
        )
        conn.execute(
            "SELECT account_id,local_date,status,event_count,attempted_at,sent_at,error "
            "FROM push_digest_deliveries LIMIT 0"
        )
    except sqlite3.OperationalError:
        return False
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
        (_REQUIRED_INDEX,),
    ).fetchone()
    return bool(row)


def install(push_module) -> None:
    """Wrap the normal migrator; never replace it with an unsafe no-op."""
    current = push_module.ensure_push_schema
    if getattr(current, "_obrasignal_fastpath", False):
        return

    def ensure_push_schema_fast(conn):
        if schema_ready(conn):
            return None
        return current(conn)

    ensure_push_schema_fast._obrasignal_fastpath = True
    ensure_push_schema_fast._obrasignal_original = current
    push_module.ensure_push_schema = ensure_push_schema_fast
