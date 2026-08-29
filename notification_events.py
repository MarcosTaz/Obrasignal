"""Account-scoped opportunity eventing and remote push delivery for ObraSignal."""
from datetime import datetime, timedelta, timezone
import hashlib
import os
import re
import secrets

import requests
from flask import jsonify, request
from jwt import InvalidTokenError

from app import APP
from auth_context import configured_identity
from auth_context_jwt import JwksUnavailableError
from decision_log import ensure_decision_table, latest_decision, latest_opportunity_current_decision
from opportunity_lifecycle import actionable_predicate, ensure_lifecycle_table


EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_RECEIPTS_URL = "https://exp.host/--/api/v2/push/getReceipts"
# Eight total send attempts span the existing 30s -> 1h exponential backoff
# ladder. There is deliberately no ninth provider replay for the same pair.
MAX_PUSH_ATTEMPTS = 8
_INSTALLATION_RE = re.compile(r"^[A-Za-z0-9._:-]{8,160}$")
_TICKET_PARENTAGE_CONFLICT = "provider_ticket_parentage_conflict"


def _norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _key(row):
    source = _norm(row.get("source"))
    external_id = _norm(row.get("external_id"))
    if external_id:
        return f"{source}:{external_id}"
    raw = "|".join(_norm(row.get(k)) for k in ("title", "buyer", "deadline", "country"))
    return f"fallback:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value):
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _next_retry_at(attempt_count, now=None):
    now = now or datetime.now(timezone.utc)
    delay_seconds = min(3600, 30 * (2 ** min(max(0, int(attempt_count) - 1), 7)))
    return (now + timedelta(seconds=delay_seconds)).isoformat()


def _retry_outcome(row, now_dt):
    """Return (next_attempt_at, failed_at) for the attempt being recorded now."""
    next_count = int(row["attempt_count"]) + 1
    if next_count >= MAX_PUSH_ATTEMPTS:
        return None, now_dt.isoformat()
    return _next_retry_at(next_count, now_dt), None


def ensure_event_table(conn):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='opportunity_events'").fetchone()
    if not exists:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS opportunity_events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL DEFAULT 'default',
                event_key TEXT NOT NULL UNIQUE,
                tender_id INTEGER,
                source TEXT,
                event_type TEXT NOT NULL,
                score INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                delivered_at TEXT
            )"""
        )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(opportunity_events)").fetchall()}
    if "account_id" not in cols:
        conn.execute("ALTER TABLE opportunity_events ADD COLUMN account_id TEXT NOT NULL DEFAULT 'default'")
    ensure_push_tables(conn)
    conn.commit()


def ensure_push_tables(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS push_devices(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            installation_id TEXT NOT NULL UNIQUE,
            expo_push_token TEXT NOT NULL UNIQUE,
            platform TEXT NOT NULL,
            binding_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_error TEXT,
            revoked_at TEXT
        )"""
    )
    device_cols = {row[1] for row in conn.execute("PRAGMA table_info(push_devices)").fetchall()}
    if "revoked_at" not in device_cols:
        conn.execute("ALTER TABLE push_devices ADD COLUMN revoked_at TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_push_devices_account ON push_devices(account_id)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS push_deliveries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            push_device_id INTEGER NOT NULL,
            ticket_id TEXT,
            submitted_at TEXT,
            last_error TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TEXT,
            next_attempt_at TEXT,
            expo_push_token TEXT,
            receipt_status TEXT,
            receipt_checked_at TEXT,
            receipt_error TEXT,
            failed_at TEXT,
            UNIQUE(event_id,push_device_id)
        )"""
    )
    delivery_cols = {row[1] for row in conn.execute("PRAGMA table_info(push_deliveries)").fetchall()}
    additions = {
        "attempt_count": "INTEGER NOT NULL DEFAULT 0",
        "last_attempt_at": "TEXT",
        "next_attempt_at": "TEXT",
        "expo_push_token": "TEXT",
        "receipt_status": "TEXT",
        "receipt_checked_at": "TEXT",
        "receipt_error": "TEXT",
        "failed_at": "TEXT",
    }
    for column, ddl in additions.items():
        if column not in delivery_cols:
            conn.execute(f"ALTER TABLE push_deliveries ADD COLUMN {column} {ddl}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_push_deliveries_event_device ON push_deliveries(event_id,push_device_id)")
    # Provider tickets are external receipt identities. Keep a separate additive
    # parent ledger so historical duplicate ticket rows can remain visible for
    # audit without being laundered into one invented authoritative parent.
    conn.execute(
        """CREATE TABLE IF NOT EXISTS push_ticket_parents(
            ticket_id TEXT PRIMARY KEY,
            push_delivery_id INTEGER NOT NULL UNIQUE,
            claimed_at TEXT NOT NULL
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_push_ticket_parent_delivery ON push_ticket_parents(push_delivery_id)")
    # Safe migration only: bind historical tickets that already have exactly one
    # local delivery parent. Duplicate historical tickets remain UNKNOWN.
    conn.execute(
        """INSERT OR IGNORE INTO push_ticket_parents(ticket_id,push_delivery_id,claimed_at)
           SELECT pd.ticket_id,pd.id,COALESCE(pd.submitted_at,pd.last_attempt_at,?)
           FROM push_deliveries pd
           WHERE pd.ticket_id IS NOT NULL
             AND TRIM(pd.ticket_id)<>''
             AND pd.submitted_at IS NOT NULL
             AND COALESCE(pd.receipt_error,'')<>?
             AND (SELECT COUNT(*) FROM push_deliveries other WHERE other.ticket_id=pd.ticket_id)=1""",
        (_iso_now(), _TICKET_PARENTAGE_CONFLICT),
    )


def _revoke_device_row(conn, device_id, *, expected_token=None, error=None):
    params = [int(device_id)]
    where = "id=?"
    if expected_token is not None:
        where += " AND expo_push_token=?"
        params.append(str(expected_token))
    row = conn.execute(f"SELECT id FROM push_devices WHERE {where}", params).fetchone()
    if not row:
        return False
    now = _iso_now()
    # Keep the durable installation row id for delivery-ledger dedupe, while
    # removing the usable provider token and rotating the opaque tap binding.
    tombstone_token = f"revoked:{row['id']}:{secrets.token_urlsafe(12)}"
    conn.execute(
        """UPDATE push_devices
           SET expo_push_token=?, binding_id=?, revoked_at=?, updated_at=?, last_error=?
           WHERE id=?""",
        (tombstone_token, secrets.token_urlsafe(24), now, now, error, row["id"]),
    )
    return True


def register_push_device(conn, account_id, installation_id, expo_push_token, platform):
    """Bind one physical app installation to exactly one authenticated account."""
    ensure_push_tables(conn)
    account_id = str(account_id or "").strip()
    installation_id = str(installation_id or "").strip()
    expo_push_token = str(expo_push_token or "").strip()
    platform = str(platform or "").strip().lower()
    if not account_id:
        raise ValueError("account_id_required")
    if not _INSTALLATION_RE.fullmatch(installation_id):
        raise ValueError("invalid_installation_id")
    if not (expo_push_token.startswith("ExpoPushToken[") or expo_push_token.startswith("ExponentPushToken[")) or len(expo_push_token) > 512:
        raise ValueError("invalid_expo_push_token")
    if platform not in ("android", "ios"):
        raise ValueError("invalid_platform")

    current = conn.execute(
        "SELECT * FROM push_devices WHERE installation_id=?",
        (installation_id,),
    ).fetchone()
    now = _iso_now()
    if current and current["revoked_at"] is None and current["account_id"] == account_id and current["expo_push_token"] == expo_push_token and current["platform"] == platform:
        conn.execute("UPDATE push_devices SET updated_at=?, last_error=NULL WHERE id=?", (now, current["id"]))
        conn.commit()
        return {"installation_id": installation_id, "binding_id": current["binding_id"], "platform": platform}

    # The physical installation is the stable delivery-ledger identity. Token
    # rotation, re-enable and A->B rebind rotate the opaque binding but keep the
    # device row id so accepted historical events cannot replay merely because
    # the provider token or account binding changed.
    binding_id = secrets.token_urlsafe(24)
    token_owner = conn.execute(
        "SELECT id FROM push_devices WHERE expo_push_token=? AND revoked_at IS NULL",
        (expo_push_token,),
    ).fetchone()
    if token_owner and (not current or token_owner["id"] != current["id"]):
        _revoke_device_row(conn, token_owner["id"], expected_token=expo_push_token, error="token_rebound")

    if current:
        conn.execute(
            """UPDATE push_devices
               SET account_id=?, expo_push_token=?, platform=?, binding_id=?, updated_at=?, last_error=NULL, revoked_at=NULL
               WHERE id=?""",
            (account_id, expo_push_token, platform, binding_id, now, current["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO push_devices(account_id,installation_id,expo_push_token,platform,binding_id,created_at,updated_at,revoked_at)
               VALUES (?,?,?,?,?,?,?,NULL)""",
            (account_id, installation_id, expo_push_token, platform, binding_id, now, now),
        )
    conn.commit()
    return {"installation_id": installation_id, "binding_id": binding_id, "platform": platform}


def unregister_push_device(conn, account_id, installation_id):
    ensure_push_tables(conn)
    row = conn.execute(
        "SELECT id FROM push_devices WHERE account_id=? AND installation_id=? AND revoked_at IS NULL",
        (str(account_id or "").strip(), str(installation_id or "").strip()),
    ).fetchone()
    if not row:
        return False
    _revoke_device_row(conn, row["id"])
    conn.commit()
    return True


def _push_headers():
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    access_token = (os.getenv("EXPO_ACCESS_TOKEN") or "").strip()
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def _finalize_exhausted_pushes(conn, account_id):
    """Normalize legacy/due rows that already exhausted the finite send budget."""
    now = _iso_now()
    cursor = conn.execute(
        """UPDATE push_deliveries
           SET failed_at=COALESCE(failed_at,?), next_attempt_at=NULL
           WHERE id IN (
             SELECT pd.id
             FROM push_deliveries pd
             JOIN opportunity_events e ON e.id=pd.event_id
             WHERE e.account_id=?
               AND pd.submitted_at IS NULL
               AND pd.failed_at IS NULL
               AND pd.attempt_count>=?
           )""",
        (now, str(account_id), MAX_PUSH_ATTEMPTS),
    )
    if cursor.rowcount:
        conn.commit()
    return cursor.rowcount


def _pending_push_rows(conn, account_id, limit=100):
    ensure_push_tables(conn)
    ensure_lifecycle_table(conn)
    rows = conn.execute(
        f"""SELECT e.id AS event_id, e.tender_id,
                   t.source AS opportunity_source, t.external_id AS opportunity_external_id,
                   d.id AS push_device_id, d.expo_push_token, d.binding_id,
                   COALESCE(pd.attempt_count,0) AS attempt_count
            FROM opportunity_events e
            JOIN tenders t ON t.id=e.tender_id
            LEFT JOIN opportunity_lifecycle lc ON lc.source=t.source AND lc.external_id=t.external_id
            JOIN push_devices d ON d.account_id=e.account_id AND d.revoked_at IS NULL
            LEFT JOIN push_deliveries pd ON pd.event_id=e.id AND pd.push_device_id=d.id
            WHERE e.account_id=?
              AND e.event_type='new_high_match'
              AND {actionable_predicate('lc', 't')}
              AND COALESCE(pd.attempt_count,0) < ?
              AND pd.submitted_at IS NULL
              AND pd.failed_at IS NULL
              AND (pd.next_attempt_at IS NULL OR datetime(pd.next_attempt_at) <= datetime('now'))
            ORDER BY e.created_at ASC, d.id ASC
            LIMIT ?""",
        (str(account_id), MAX_PUSH_ATTEMPTS, max(1, min(100, int(limit)))),
    ).fetchall()
    eligible = []
    for row in rows:
        historical_decision = latest_decision(
            conn,
            row["opportunity_source"],
            row["opportunity_external_id"],
            account_id=account_id,
        )
        if historical_decision is None:
            eligible.append(row)
            continue
        if latest_opportunity_current_decision(
            conn,
            row["opportunity_source"],
            row["opportunity_external_id"],
            account_id=account_id,
        ) is not None:
            eligible.append(row)
    return eligible


def _record_push_attempt(conn, row, *, ticket_id=None, submitted_at=None, error=None, attempted_at=None, next_attempt_at=None, failed_at=None):
    attempted_at = attempted_at or _iso_now()
    conn.execute(
        """INSERT INTO push_deliveries(
               event_id,push_device_id,ticket_id,submitted_at,last_error,attempt_count,last_attempt_at,
               next_attempt_at,expo_push_token,receipt_status,receipt_checked_at,receipt_error,failed_at
           ) VALUES (?,?,?,?,?,1,?,?,?,NULL,NULL,NULL,?)
           ON CONFLICT(event_id,push_device_id) DO UPDATE SET
             ticket_id=excluded.ticket_id,
             submitted_at=excluded.submitted_at,
             last_error=excluded.last_error,
             attempt_count=push_deliveries.attempt_count+1,
             last_attempt_at=excluded.last_attempt_at,
             next_attempt_at=excluded.next_attempt_at,
             expo_push_token=excluded.expo_push_token,
             receipt_status=NULL,
             receipt_checked_at=NULL,
             receipt_error=NULL,
             failed_at=excluded.failed_at""",
        (
            row["event_id"], row["push_device_id"], ticket_id, submitted_at, error,
            attempted_at, next_attempt_at, row["expo_push_token"], failed_at,
        ),
    )


def _claim_provider_ticket_parent(conn, row, ticket_id, claimed_at=None):
    """Bind one provider ticket to one exact local delivery or fail closed."""
    ticket_id = str(ticket_id or "").strip()
    if not ticket_id:
        return False
    local = conn.execute(
        "SELECT id FROM push_deliveries WHERE event_id=? AND push_device_id=? AND ticket_id=?",
        (row["event_id"], row["push_device_id"], ticket_id),
    ).fetchone()
    if not local:
        return False
    count = conn.execute("SELECT COUNT(*) FROM push_deliveries WHERE ticket_id=?", (ticket_id,)).fetchone()[0]
    if int(count) != 1:
        return False
    conn.execute(
        "INSERT OR IGNORE INTO push_ticket_parents(ticket_id,push_delivery_id,claimed_at) VALUES (?,?,?)",
        (ticket_id, local["id"], claimed_at or _iso_now()),
    )
    owner = conn.execute(
        "SELECT push_delivery_id FROM push_ticket_parents WHERE ticket_id=?",
        (ticket_id,),
    ).fetchone()
    return bool(owner and int(owner["push_delivery_id"]) == int(local["id"]))


def _mark_ticket_parentage_conflict(conn, ticket_id, now=None):
    """Preserve ambiguous provider evidence but make it non-authoritative."""
    ticket_id = str(ticket_id or "").strip()
    if not ticket_id:
        return 0
    now = now or _iso_now()
    conn.execute("DELETE FROM push_ticket_parents WHERE ticket_id=?", (ticket_id,))
    cursor = conn.execute(
        """UPDATE push_deliveries
           SET receipt_status='error',receipt_checked_at=?,receipt_error=?,last_error=?,
               failed_at=COALESCE(failed_at,?),next_attempt_at=NULL
           WHERE ticket_id=?""",
        (now, _TICKET_PARENTAGE_CONFLICT, _TICKET_PARENTAGE_CONFLICT, now, ticket_id),
    )
    return cursor.rowcount


def submit_pending_pushes(conn, account_id, limit=100, post=requests.post):
    """Submit pending account-scoped events to Expo; retries terminate after the owner budget."""
    _finalize_exhausted_pushes(conn, account_id)
    rows = _pending_push_rows(conn, account_id, limit=limit)
    if not rows:
        return 0
    messages = [
        {
            "to": row["expo_push_token"],
            "title": "Nova oportunidade ObraSignal",
            # Never put tenant-specific opportunity content in the OS tray.
            # An offline sign-out may leave a stale server token temporarily;
            # the opaque binding is validated in-app before current detail is fetched.
            "body": "Abre o ObraSignal para confirmar uma nova oportunidade.",
            "data": {
                "opportunityId": row["tender_id"],
                "eventId": row["event_id"],
                "bindingId": row["binding_id"],
            },
            "priority": "high",
        }
        for row in rows
    ]
    try:
        response = post(EXPO_PUSH_URL, json=messages, headers=_push_headers(), timeout=8)
        response.raise_for_status()
        payload = response.json() or {}
        tickets = payload.get("data") or []
        if not isinstance(tickets, list):
            tickets = []
    except Exception as exc:
        # Event persistence remains authoritative and ingestion/bootstrap must not
        # fail. Persist a bounded error class and stop retrying after attempt 8.
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        error = f"transport_{type(exc).__name__}"[:240]
        for row in rows:
            retry_at, failed_at = _retry_outcome(row, now_dt)
            _record_push_attempt(
                conn,
                row,
                error=error,
                attempted_at=now,
                next_attempt_at=retry_at,
                failed_at=failed_at,
            )
            conn.execute("UPDATE push_devices SET last_error=? WHERE id=?", (error, row["push_device_id"]))
        conn.commit()
        return 0

    # Detect duplicate provider ticket identities in the same response before any
    # one row can claim authority. A duplicate provider id means causal parentage
    # is UNKNOWN even if Expo accepted every payload.
    ticket_counts = {}
    for ticket in tickets:
        if not isinstance(ticket, dict) or ticket.get("status") != "ok":
            continue
        ticket_id = str(ticket.get("id") or "").strip()
        if ticket_id:
            ticket_counts[ticket_id] = ticket_counts.get(ticket_id, 0) + 1

    submitted = 0
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    for index, row in enumerate(rows):
        ticket = tickets[index] if index < len(tickets) else None
        status = ticket.get("status") if isinstance(ticket, dict) else None
        ticket_id = str(ticket.get("id") or "").strip() if isinstance(ticket, dict) else ""
        if status == "ok" and ticket_id:
            _record_push_attempt(conn, row, ticket_id=ticket_id, submitted_at=now, attempted_at=now)
            if ticket_counts.get(ticket_id, 0) != 1 or not _claim_provider_ticket_parent(conn, row, ticket_id, now):
                _mark_ticket_parentage_conflict(conn, ticket_id, now)
                conn.execute(
                    "UPDATE push_devices SET last_error=? WHERE id=?",
                    (_TICKET_PARENTAGE_CONFLICT, row["push_device_id"]),
                )
                continue
            conn.execute("UPDATE push_devices SET last_error=NULL WHERE id=?", (row["push_device_id"],))
            submitted += 1
            continue

        if status == "ok":
            # A provider acknowledgement without a ticket id cannot be reconciled
            # to a receipt, so never record it as a successful submission.
            error = "push_response_missing_ticket"
        else:
            details = ticket.get("details") if isinstance(ticket, dict) else {}
            error = (details or {}).get("error") or (ticket.get("message") if isinstance(ticket, dict) else None) or "push_response_missing_ticket"
            error = str(error)[:240]
        if error == "DeviceNotRegistered":
            _record_push_attempt(conn, row, error=error, attempted_at=now, failed_at=now)
            _revoke_device_row(conn, row["push_device_id"], expected_token=row["expo_push_token"], error=error)
        elif error == "push_response_missing_ticket":
            retry_at, failed_at = _retry_outcome(row, now_dt)
            _record_push_attempt(
                conn,
                row,
                error=error,
                attempted_at=now,
                next_attempt_at=retry_at,
                failed_at=failed_at,
            )
            conn.execute("UPDATE push_devices SET last_error=? WHERE id=?", (error, row["push_device_id"]))
        else:
            # Individual ticket rejection means Expo did not accept the payload;
            # retain the terminal error rather than spinning the same bad request.
            _record_push_attempt(conn, row, error=error, attempted_at=now, failed_at=now)
            conn.execute("UPDATE push_devices SET last_error=? WHERE id=?", (error, row["push_device_id"]))
    conn.commit()
    return submitted


def reconcile_push_receipts(conn, account_id, limit=1000, post=requests.post, min_age_seconds=900):
    """Reconcile Expo tickets to provider receipts without claiming device/user delivery."""
    ensure_push_tables(conn)
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    # Parentage is global to the external ticket identity, not tenant-local. Any
    # duplicate historical/current ticket is made terminally non-authoritative
    # before the provider is queried, so one receipt can never fan out.
    duplicate_tickets = conn.execute(
        """SELECT ticket_id FROM push_deliveries
           WHERE ticket_id IS NOT NULL AND TRIM(ticket_id)<>''
           GROUP BY ticket_id HAVING COUNT(*)>1"""
    ).fetchall()
    for duplicate in duplicate_tickets:
        _mark_ticket_parentage_conflict(conn, duplicate["ticket_id"], now)
    if duplicate_tickets:
        conn.commit()

    candidates = conn.execute(
        """SELECT pd.id,pd.event_id,pd.push_device_id,pd.ticket_id,pd.submitted_at,
                  pd.receipt_checked_at,pd.expo_push_token,pd.attempt_count
           FROM push_deliveries pd
           JOIN opportunity_events e ON e.id=pd.event_id
           JOIN push_ticket_parents ptp
             ON ptp.ticket_id=pd.ticket_id AND ptp.push_delivery_id=pd.id
           WHERE e.account_id=?
             AND pd.ticket_id IS NOT NULL
             AND pd.submitted_at IS NOT NULL
             AND pd.receipt_status IS NULL
           ORDER BY pd.submitted_at ASC
           LIMIT ?""",
        (str(account_id), max(1, min(1000, int(limit)))),
    ).fetchall()
    if not candidates:
        return 0

    due = []
    for row in candidates:
        reference = _parse_iso(row["receipt_checked_at"]) or _parse_iso(row["submitted_at"])
        if reference is None or (now_dt - reference).total_seconds() >= max(0, int(min_age_seconds)):
            due.append(row)
    if not due:
        return 0

    try:
        response = post(
            EXPO_RECEIPTS_URL,
            json={"ids": [row["ticket_id"] for row in due]},
            headers=_push_headers(),
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json() or {}
        receipts = payload.get("data") or {}
        if not isinstance(receipts, dict):
            receipts = {}
    except Exception as exc:
        now = now_dt.isoformat()
        error = f"receipt_transport_{type(exc).__name__}"[:240]
        for row in due:
            conn.execute(
                "UPDATE push_deliveries SET receipt_checked_at=?,last_error=? WHERE id=?",
                (now, error, row["id"]),
            )
        conn.commit()
        return 0

    reconciled = 0
    now = now_dt.isoformat()
    for row in due:
        receipt = receipts.get(row["ticket_id"])
        if not isinstance(receipt, dict):
            # Expo documents missing receipts as possible while processing; after
            # the recommended wait this is observable but remains re-checkable.
            conn.execute(
                "UPDATE push_deliveries SET receipt_checked_at=?,last_error=? WHERE id=?",
                (now, "receipt_not_available", row["id"]),
            )
            continue

        status = receipt.get("status")
        if status == "ok":
            # provider_accepted means FCM/APNs accepted the notification. It is
            # deliberately not named delivered: the device/user may not receive it.
            conn.execute(
                """UPDATE push_deliveries
                   SET receipt_status='provider_accepted',receipt_checked_at=?,receipt_error=NULL,last_error=NULL,next_attempt_at=NULL
                   WHERE id=?""",
                (now, row["id"]),
            )
            reconciled += 1
            continue

        details = receipt.get("details") or {}
        error = str(details.get("error") or receipt.get("message") or "receipt_error")[:240]
        if error == "MessageRateExceeded" and int(row["attempt_count"]) < MAX_PUSH_ATTEMPTS:
            # Expo explicitly recommends exponential backoff and retry for this
            # receipt state, but the local owner budget still forbids replay > 8.
            retry_at = _next_retry_at(int(row["attempt_count"]) + 1, now_dt)
            conn.execute(
                "DELETE FROM push_ticket_parents WHERE ticket_id=? AND push_delivery_id=?",
                (row["ticket_id"], row["id"]),
            )
            conn.execute(
                """UPDATE push_deliveries
                   SET ticket_id=NULL,submitted_at=NULL,last_error=?,next_attempt_at=?,
                       receipt_status=NULL,receipt_checked_at=?,receipt_error=?,failed_at=NULL
                   WHERE id=?""",
                (error, retry_at, now, error, row["id"]),
            )
        else:
            conn.execute(
                """UPDATE push_deliveries
                   SET receipt_status='error',receipt_checked_at=?,receipt_error=?,last_error=?,failed_at=?,next_attempt_at=NULL
                   WHERE id=?""",
                (now, error, error, now, row["id"]),
            )
            if error == "DeviceNotRegistered" and row["expo_push_token"]:
                # Receipt is delayed. Revoke only if this exact token is still on
                # the stable device row; never revoke a newly rotated valid token.
                _revoke_device_row(
                    conn,
                    row["push_device_id"],
                    expected_token=row["expo_push_token"],
                    error=error,
                )
        reconciled += 1
    conn.commit()
    return reconciled


def record_new_opportunities(conn, account_id="default", min_score=75):
    """Record high-value, currently actionable opportunities for one account."""
    account_id = str(account_id or "default")
    ensure_event_table(conn)
    ensure_decision_table(conn)
    ensure_lifecycle_table(conn)
    rows = conn.execute(
        f"""SELECT t.*, d.score AS account_score
           FROM tenders t
           JOIN (
               SELECT source, external_id, MAX(id) AS max_id
               FROM opportunity_decisions
               WHERE account_id=?
               GROUP BY source, external_id
           ) latest ON latest.source=t.source AND latest.external_id=t.external_id
           JOIN opportunity_decisions d ON d.id=latest.max_id
           LEFT JOIN opportunity_lifecycle lc
             ON lc.source=t.source AND lc.external_id=t.external_id
           WHERE t.first_seen IS NOT NULL
             AND t.first_seen >= datetime('now','-2 minutes')
             AND d.score >= ?
             AND {actionable_predicate('lc', 't')}
           ORDER BY d.score DESC, t.first_seen ASC""",
        (account_id, min_score),
    ).fetchall()
    events = []
    now = _iso_now()
    for row in rows:
        d = dict(row)
        if latest_opportunity_current_decision(
            conn,
            d.get("source"),
            d.get("external_id"),
            account_id=account_id,
        ) is None:
            continue
        base_key = _key(d)
        event_key = f"{account_id}:{base_key}"
        account_score = d.get("account_score", 0)
        cur = conn.execute(
            """INSERT OR IGNORE INTO opportunity_events
               (account_id,event_key,tender_id,source,event_type,score,created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (account_id, event_key, d.get("id"), d.get("source"), "new_high_match", account_score, now),
        )
        if cur.rowcount:
            events.append({
                "event_key": event_key,
                "account_id": account_id,
                "tender_id": d.get("id"),
                "source": d.get("source"),
                "score": account_score,
                "title": d.get("title"),
                "country": d.get("country"),
                "url": d.get("url"),
            })
    conn.commit()
    # Reconcile older accepted tickets first, then retry/new-submit due pairs.
    # Neither step can promote an Expo/FCM/APNs acknowledgement to user delivery.
    try:
        reconcile_push_receipts(conn, account_id)
    except Exception as exc:
        APP.logger.warning("push receipt reconciliation failed: %s", type(exc).__name__)
    submit_pending_pushes(conn, account_id)
    return events


def _push_identity():
    try:
        return configured_identity(), None
    except JwksUnavailableError:
        return None, (jsonify({"error": "authentication_service_unavailable"}), 503)
    except (RuntimeError, InvalidTokenError):
        return None, (jsonify({"error": "authentication_required"}), 401)


@APP.route("/api/v1/push/devices", methods=["POST", "DELETE"])
def push_devices_api():
    identity, error = _push_identity()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    installation_id = str(payload.get("installation_id") or "").strip()
    conn = APP.config.get("OBRASIGNAL_DB_CONNECT")() if callable(APP.config.get("OBRASIGNAL_DB_CONNECT")) else None
    if conn is None:
        import app as _app
        conn = _app.db()
    try:
        if request.method == "DELETE":
            removed = unregister_push_device(conn, identity.account_id, installation_id)
            return jsonify({"ok": True, "removed": removed})
        try:
            registered = register_push_device(
                conn,
                identity.account_id,
                installation_id,
                payload.get("expo_push_token"),
                payload.get("platform"),
            )
        except ValueError:
            return jsonify({"error": "invalid_push_device_request"}), 400
        return jsonify({"ok": True, **registered})
    finally:
        conn.close()
