"""Account-scoped opportunity eventing and remote push delivery for ObraSignal."""
from datetime import datetime, timezone
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
from opportunity_lifecycle import actionable_predicate, ensure_lifecycle_table


EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
_INSTALLATION_RE = re.compile(r"^[A-Za-z0-9._:-]{8,160}$")


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
            last_error TEXT
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_push_devices_account ON push_devices(account_id)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS push_deliveries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            push_device_id INTEGER NOT NULL,
            ticket_id TEXT,
            submitted_at TEXT,
            last_error TEXT,
            UNIQUE(event_id,push_device_id)
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_push_deliveries_event_device ON push_deliveries(event_id,push_device_id)")


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
    if current and current["account_id"] == account_id and current["expo_push_token"] == expo_push_token and current["platform"] == platform:
        conn.execute("UPDATE push_devices SET updated_at=?, last_error=NULL WHERE id=?", (now, current["id"]))
        conn.commit()
        return {"installation_id": installation_id, "binding_id": current["binding_id"], "platform": platform}

    # One installation/token can never remain attached to Account A after it is
    # rebound by an authenticated Account B request.
    conn.execute("DELETE FROM push_devices WHERE installation_id=? OR expo_push_token=?", (installation_id, expo_push_token))
    binding_id = secrets.token_urlsafe(24)
    conn.execute(
        """INSERT INTO push_devices(account_id,installation_id,expo_push_token,platform,binding_id,created_at,updated_at)
           VALUES (?,?,?,?,?,?,?)""",
        (account_id, installation_id, expo_push_token, platform, binding_id, now, now),
    )
    conn.commit()
    return {"installation_id": installation_id, "binding_id": binding_id, "platform": platform}


def unregister_push_device(conn, account_id, installation_id):
    ensure_push_tables(conn)
    cur = conn.execute(
        "DELETE FROM push_devices WHERE account_id=? AND installation_id=?",
        (str(account_id or "").strip(), str(installation_id or "").strip()),
    )
    conn.commit()
    return bool(cur.rowcount)


def _push_headers():
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    access_token = (os.getenv("EXPO_ACCESS_TOKEN") or "").strip()
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def _pending_push_rows(conn, account_id, limit=100):
    ensure_push_tables(conn)
    ensure_lifecycle_table(conn)
    return conn.execute(
        f"""SELECT e.id AS event_id, e.tender_id,
                   d.id AS push_device_id, d.expo_push_token, d.binding_id
            FROM opportunity_events e
            JOIN tenders t ON t.id=e.tender_id
            LEFT JOIN opportunity_lifecycle lc ON lc.source=t.source AND lc.external_id=t.external_id
            JOIN push_devices d ON d.account_id=e.account_id
            LEFT JOIN push_deliveries pd ON pd.event_id=e.id AND pd.push_device_id=d.id
            WHERE e.account_id=?
              AND e.event_type='new_high_match'
              AND {actionable_predicate('lc', 't')}
              AND pd.submitted_at IS NULL
            ORDER BY e.created_at ASC, d.id ASC
            LIMIT ?""",
        (str(account_id), max(1, min(100, int(limit)))),
    ).fetchall()


def submit_pending_pushes(conn, account_id, limit=100, post=requests.post):
    """Submit undelivered account-scoped events to Expo; retry transient failures later."""
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
    except Exception:
        # Do not fail ingestion. With no submitted_at row, the next sync retries.
        return 0

    submitted = 0
    now = _iso_now()
    for row, ticket in zip(rows, tickets):
        status = ticket.get("status") if isinstance(ticket, dict) else None
        if status == "ok":
            conn.execute(
                """INSERT INTO push_deliveries(event_id,push_device_id,ticket_id,submitted_at,last_error)
                   VALUES (?,?,?,?,NULL)
                   ON CONFLICT(event_id,push_device_id) DO UPDATE SET
                     ticket_id=excluded.ticket_id, submitted_at=excluded.submitted_at, last_error=NULL""",
                (row["event_id"], row["push_device_id"], ticket.get("id"), now),
            )
            conn.execute("UPDATE push_devices SET last_error=NULL WHERE id=?", (row["push_device_id"],))
            submitted += 1
            continue

        details = ticket.get("details") if isinstance(ticket, dict) else {}
        error = (details or {}).get("error") or (ticket.get("message") if isinstance(ticket, dict) else None) or "push_rejected"
        if error == "DeviceNotRegistered":
            conn.execute("DELETE FROM push_devices WHERE id=?", (row["push_device_id"],))
        else:
            conn.execute("UPDATE push_devices SET last_error=? WHERE id=?", (str(error)[:240], row["push_device_id"]))
            conn.execute(
                """INSERT INTO push_deliveries(event_id,push_device_id,last_error)
                   VALUES (?,?,?)
                   ON CONFLICT(event_id,push_device_id) DO UPDATE SET last_error=excluded.last_error""",
                (row["event_id"], row["push_device_id"], str(error)[:240]),
            )
    conn.commit()
    return submitted


def record_new_opportunities(conn, account_id="default", min_score=75):
    """Record high-value, currently actionable opportunities for one account."""
    account_id = str(account_id or "default")
    ensure_event_table(conn)
    ensure_lifecycle_table(conn)
    rows = conn.execute(
        f"""SELECT t.* FROM tenders t
           LEFT JOIN opportunity_lifecycle lc
             ON lc.source=t.source AND lc.external_id=t.external_id
           WHERE t.first_seen IS NOT NULL
             AND t.first_seen >= datetime('now','-2 minutes')
             AND t.score >= ?
             AND {actionable_predicate('lc', 't')}
           ORDER BY t.score DESC, t.first_seen ASC""",
        (min_score,),
    ).fetchall()
    events = []
    now = _iso_now()
    for row in rows:
        d = dict(row)
        base_key = _key(d)
        event_key = f"{account_id}:{base_key}"
        cur = conn.execute(
            """INSERT OR IGNORE INTO opportunity_events
               (account_id,event_key,tender_id,source,event_type,score,created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (account_id, event_key, d.get("id"), d.get("source"), "new_high_match", d.get("score", 0), now),
        )
        if cur.rowcount:
            events.append({
                "event_key": event_key,
                "account_id": account_id,
                "tender_id": d.get("id"),
                "source": d.get("source"),
                "score": d.get("score", 0),
                "title": d.get("title"),
                "country": d.get("country"),
                "url": d.get("url"),
            })
    conn.commit()
    # Event persistence is authoritative. Push transport is best-effort and can
    # retry pending event/device pairs on the next sync without duplicating an
    # accepted submission.
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
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"ok": True, **registered})
    finally:
        conn.close()
