"""Fail-closed guard for the provider-send/local-ledger crash boundary.

Expo does not provide ObraSignal with an end-to-end idempotency key. A process
can therefore die after a provider request has been accepted but before the
local ticket/attempt is committed. Replaying that pair automatically can create
a duplicate irreversible provider side effect.

This guard uses the existing ``push_deliveries`` row as a durable dispatch intent
without adding a second persistence authority or schema. Before the provider
call, each currently pending pair is marked ``dispatch_started_unresolved`` and
committed while leaving ``attempt_count`` unchanged so the existing owner retry
logic remains authoritative on normal completion.

If a later process finds that marker still unresolved, whether the prior process
died just before or just after the provider call is unknowable. The pair is
therefore terminalized as ``ambiguous_provider_state`` and is not automatically
replayed. This intentionally prefers a possible missed push over a duplicate
push; current Radar remains the authoritative customer surface.
"""
from __future__ import annotations

import notification_events as _events

DISPATCH_STARTED = "dispatch_started_unresolved"
AMBIGUOUS_PROVIDER_STATE = "ambiguous_provider_state"
_ORIGINAL_SUBMIT = _events.submit_pending_pushes
_INSTALLED = False


def _terminalize_unresolved_dispatches(conn, account_id):
    """Convert crash-surviving dispatch intents into terminal ambiguity."""
    _events.ensure_push_tables(conn)
    rows = conn.execute(
        """SELECT pd.id,pd.attempt_count
           FROM push_deliveries pd
           JOIN opportunity_events e ON e.id=pd.event_id
           WHERE e.account_id=?
             AND pd.submitted_at IS NULL
             AND pd.failed_at IS NULL
             AND pd.last_error=?""",
        (str(account_id), DISPATCH_STARTED),
    ).fetchall()
    if not rows:
        return 0
    now = _events._iso_now()
    for row in rows:
        conn.execute(
            """UPDATE push_deliveries
               SET attempt_count=CASE WHEN attempt_count < ? THEN attempt_count+1 ELSE attempt_count END,
                   last_error=?,last_attempt_at=COALESCE(last_attempt_at,?),
                   next_attempt_at=NULL,failed_at=?
               WHERE id=?""",
            (
                _events.MAX_PUSH_ATTEMPTS,
                AMBIGUOUS_PROVIDER_STATE,
                now,
                now,
                row["id"],
            ),
        )
    conn.commit()
    return len(rows)


def _persist_dispatch_intents(conn, rows):
    """Durably mark provider-call intent without consuming an attempt yet."""
    if not rows:
        return 0
    now = _events._iso_now()
    for row in rows:
        conn.execute(
            """INSERT INTO push_deliveries(
                   event_id,push_device_id,attempt_count,last_error,last_attempt_at,
                   next_attempt_at,expo_push_token,failed_at,submitted_at
               ) VALUES (?,?,?, ?,?,NULL,?,NULL,NULL)
               ON CONFLICT(event_id,push_device_id) DO UPDATE SET
                 last_error=excluded.last_error,
                 last_attempt_at=excluded.last_attempt_at,
                 next_attempt_at=NULL,
                 expo_push_token=excluded.expo_push_token,
                 failed_at=NULL""",
            (
                row["event_id"],
                row["push_device_id"],
                int(row["attempt_count"]),
                DISPATCH_STARTED,
                now,
                row["expo_push_token"],
            ),
        )
    conn.commit()
    return len(rows)


def _clear_unconsumed_dispatch_intents(conn, rows):
    """Remove intents that the owner recheck rejected before any provider attempt.

    The owner submit path always replaces ``DISPATCH_STARTED`` when it actually
    attempts a provider request, including transport failures and ticket errors.
    Therefore a marker that still survives after the owner function returns
    normally proves that the pair was re-selected out before the provider
    boundary (for example because canonical opportunity authority went stale).
    Such a row is not ambiguous and must not survive as a false dispatch record.
    A process crash still bypasses this cleanup and preserves the original
    fail-closed ambiguity contract.
    """
    removed = 0
    for row in rows:
        cursor = conn.execute(
            """DELETE FROM push_deliveries
               WHERE event_id=? AND push_device_id=?
                 AND submitted_at IS NULL
                 AND failed_at IS NULL
                 AND last_error=?
                 AND attempt_count=?""",
            (
                row["event_id"],
                row["push_device_id"],
                DISPATCH_STARTED,
                int(row["attempt_count"]),
            ),
        )
        removed += cursor.rowcount
    if removed:
        conn.commit()
    return removed


def submit_pending_pushes(conn, account_id, limit=100, post=None):
    """Submit with durable intent before any external provider side effect."""
    account_id = str(account_id)
    _terminalize_unresolved_dispatches(conn, account_id)
    _events._finalize_exhausted_pushes(conn, account_id)
    rows = _events._pending_push_rows(conn, account_id, limit=limit)
    if not rows:
        return 0
    _persist_dispatch_intents(conn, rows)

    # The original owner function re-selects the same still-pending rows and
    # owns all normal ticket/error/retry semantics. Its first durable attempt
    # write clears the intent marker. If execution dies before that write, the
    # marker survives for fail-closed reconciliation on restart.
    if post is None:
        submitted = _ORIGINAL_SUBMIT(conn, account_id, limit=limit)
    else:
        submitted = _ORIGINAL_SUBMIT(conn, account_id, limit=limit, post=post)

    # If the owner recheck dropped any pair before a provider attempt, its
    # dispatch marker remains untouched. Remove only those exact untouched
    # markers after normal owner return; provider-attempt rows have already
    # changed state and crash-surviving markers never reach this cleanup.
    _clear_unconsumed_dispatch_intents(conn, rows)
    return submitted


def install():
    """Install at the production boundary without redefining Notification APIs."""
    global _INSTALLED
    if _INSTALLED or _events.submit_pending_pushes is submit_pending_pushes:
        _INSTALLED = True
        return False
    _events.submit_pending_pushes = submit_pending_pushes
    _INSTALLED = True
    return True
