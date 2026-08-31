"""Server-authoritative push notification delivery for ObraSignal.

Native clients register an Expo push token plus timezone. A single production
scheduler sends one morning digest per account/local-day even when the app is
closed. Delivery state is independent from the in-app unread marker so opening
one device cannot suppress another device's morning push.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import re
import threading
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from flask import Blueprint, jsonify, request

from auth_context import configured_identity, InvalidTokenError
from opportunity_lifecycle import actionable_predicate, ensure_lifecycle_table

bp = Blueprint("push_runtime", __name__, url_prefix="/api/v1/push")
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
DEFAULT_TIMEZONE = "Europe/Lisbon"
DEFAULT_LOCAL_HOUR = 8
DEFAULT_LOCAL_MINUTE = 0
MAX_CATCHUP_MINUTES = 180
PUSH_TOKEN_RE = re.compile(r"^(?:Expo|Exponent)PushToken\[[A-Za-z0-9_-]+\]$")
_scheduler_lock = threading.Lock()
_scheduler_started = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db():
    from app import db
    return db()


def ensure_push_schema(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS push_devices(
            token TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            timezone TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_push_devices_account ON push_devices(account_id, enabled)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS push_preferences(
            account_id TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 0,
            timezone TEXT NOT NULL DEFAULT 'Europe/Lisbon',
            local_hour INTEGER NOT NULL DEFAULT 8,
            local_minute INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS push_digest_deliveries(
            account_id TEXT NOT NULL,
            local_date TEXT NOT NULL,
            status TEXT NOT NULL,
            event_count INTEGER NOT NULL DEFAULT 0,
            attempted_at TEXT NOT NULL,
            sent_at TEXT,
            error TEXT,
            PRIMARY KEY(account_id, local_date)
        )"""
    )
    conn.commit()


def _valid_timezone(value: object) -> str:
    candidate = str(value or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    if len(candidate) > 80:
        raise ValueError("invalid_timezone")
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("invalid_timezone") from exc
    return candidate


def _valid_schedule(hour: object, minute: object) -> tuple[int, int]:
    try:
        h = int(DEFAULT_LOCAL_HOUR if hour is None else hour)
        m = int(DEFAULT_LOCAL_MINUTE if minute is None else minute)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_schedule") from exc
    if h not in (7, 8) or not (0 <= m <= 59):
        raise ValueError("invalid_schedule")
    return h, m


def _identity():
    try:
        return configured_identity()
    except (RuntimeError, InvalidTokenError):
        return None


def _preference(conn, account_id: str) -> dict:
    ensure_push_schema(conn)
    row = conn.execute("SELECT * FROM push_preferences WHERE account_id=?", (str(account_id),)).fetchone()
    if not row:
        return {
            "account_id": str(account_id), "enabled": False, "timezone": DEFAULT_TIMEZONE,
            "local_hour": DEFAULT_LOCAL_HOUR, "local_minute": DEFAULT_LOCAL_MINUTE,
        }
    out = dict(row)
    out["enabled"] = bool(out.get("enabled"))
    return out


def set_preference(conn, account_id: str, *, enabled: bool, timezone_name: str,
                   local_hour: int = DEFAULT_LOCAL_HOUR, local_minute: int = DEFAULT_LOCAL_MINUTE) -> dict:
    ensure_push_schema(conn)
    timezone_name = _valid_timezone(timezone_name)
    local_hour, local_minute = _valid_schedule(local_hour, local_minute)
    conn.execute(
        """INSERT INTO push_preferences(account_id,enabled,timezone,local_hour,local_minute,updated_at)
           VALUES(?,?,?,?,?,?)
           ON CONFLICT(account_id) DO UPDATE SET enabled=excluded.enabled, timezone=excluded.timezone,
             local_hour=excluded.local_hour, local_minute=excluded.local_minute, updated_at=excluded.updated_at""",
        (str(account_id), 1 if enabled else 0, timezone_name, local_hour, local_minute, _now_iso()),
    )
    if not enabled:
        conn.execute("UPDATE push_devices SET enabled=0 WHERE account_id=?", (str(account_id),))
    conn.commit()
    return _preference(conn, account_id)


def register_device(conn, account_id: str, *, token: str, platform: str, timezone_name: str) -> dict:
    ensure_push_schema(conn)
    token = str(token or "").strip()
    platform = str(platform or "").strip().lower()
    timezone_name = _valid_timezone(timezone_name)
    if not PUSH_TOKEN_RE.fullmatch(token) or len(token) > 512:
        raise ValueError("invalid_push_token")
    if platform not in {"ios", "android"}:
        raise ValueError("invalid_platform")
    now = _now_iso()
    # Token ownership follows the currently authenticated account. If a shared
    # device logs into another tenant, this atomically removes the old routing.
    conn.execute(
        """INSERT INTO push_devices(token,account_id,platform,timezone,enabled,created_at,last_seen_at)
           VALUES(?,?,?,?,1,?,?)
           ON CONFLICT(token) DO UPDATE SET account_id=excluded.account_id, platform=excluded.platform,
             timezone=excluded.timezone, enabled=1, last_seen_at=excluded.last_seen_at""",
        (token, str(account_id), platform, timezone_name, now, now),
    )
    pref = _preference(conn, account_id)
    conn.execute(
        """INSERT INTO push_preferences(account_id,enabled,timezone,local_hour,local_minute,updated_at)
           VALUES(?,1,?,?,?,?)
           ON CONFLICT(account_id) DO UPDATE SET enabled=1, timezone=excluded.timezone, updated_at=excluded.updated_at""",
        (str(account_id), timezone_name, pref["local_hour"], pref["local_minute"], now),
    )
    conn.commit()
    return {"registered": True, "timezone": timezone_name, "platform": platform}


def unregister_account_devices(conn, account_id: str) -> int:
    ensure_push_schema(conn)
    cur = conn.execute("UPDATE push_devices SET enabled=0 WHERE account_id=?", (str(account_id),))
    conn.execute(
        """INSERT INTO push_preferences(account_id,enabled,timezone,local_hour,local_minute,updated_at)
           VALUES(?,0,?,?,?,?)
           ON CONFLICT(account_id) DO UPDATE SET enabled=0, updated_at=excluded.updated_at""",
        (str(account_id), DEFAULT_TIMEZONE, DEFAULT_LOCAL_HOUR, DEFAULT_LOCAL_MINUTE, _now_iso()),
    )
    conn.commit()
    return int(cur.rowcount or 0)


@bp.post("/preference")
def push_preference():
    identity = _identity()
    if identity is None:
        return jsonify({"error": "authentication_required"}), 401
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict) or not isinstance(body.get("enabled"), bool):
        return jsonify({"error": "invalid_push_preference"}), 400
    try:
        tz = _valid_timezone(body.get("timezone"))
        h, m = _valid_schedule(body.get("local_hour"), body.get("local_minute"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    conn = _db()
    try:
        pref = set_preference(conn, identity.account_id, enabled=body["enabled"], timezone_name=tz,
                              local_hour=h, local_minute=m)
        return jsonify({"ok": True, "preference": pref, "account_id": identity.account_id})
    finally:
        conn.close()


@bp.post("/device")
def push_device():
    identity = _identity()
    if identity is None:
        return jsonify({"error": "authentication_required"}), 401
    body = request.get_json(silent=True) or {}
    conn = _db()
    try:
        try:
            result = register_device(
                conn, identity.account_id, token=body.get("token"),
                platform=body.get("platform"), timezone_name=body.get("timezone"),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"ok": True, **result, "account_id": identity.account_id})
    finally:
        conn.close()


def unregister_device(conn, account_id: str, token: str) -> int:
    ensure_push_schema(conn)
    token = str(token or "").strip()
    if not PUSH_TOKEN_RE.fullmatch(token):
        raise ValueError("invalid_push_token")
    cur = conn.execute(
        "UPDATE push_devices SET enabled=0 WHERE account_id=? AND token=?",
        (str(account_id), token),
    )
    conn.commit()
    return int(cur.rowcount or 0)


@bp.delete("/device")
def push_device_delete():
    identity = _identity()
    if identity is None:
        return jsonify({"error": "authentication_required"}), 401
    body = request.get_json(silent=True) or {}
    conn = _db()
    try:
        token = body.get("token") if isinstance(body, dict) else None
        try:
            disabled = unregister_device(conn, identity.account_id, token) if token else unregister_account_devices(conn, identity.account_id)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"ok": True, "disabled_devices": disabled, "account_id": identity.account_id})
    finally:
        conn.close()


@bp.get("/status")
def push_status():
    identity = _identity()
    if identity is None:
        return jsonify({"error": "authentication_required"}), 401
    conn = _db()
    try:
        pref = _preference(conn, identity.account_id)
        devices = conn.execute(
            "SELECT platform,timezone,last_seen_at FROM push_devices WHERE account_id=? AND enabled=1 ORDER BY last_seen_at DESC",
            (str(identity.account_id),),
        ).fetchall()
        return jsonify({"preference": pref, "devices": [dict(row) for row in devices], "account_id": identity.account_id})
    finally:
        conn.close()


def _due(pref: dict, now_utc: datetime) -> tuple[bool, str, datetime]:
    tz = ZoneInfo(pref["timezone"])
    local_now = now_utc.astimezone(tz)
    target = local_now.replace(hour=int(pref["local_hour"]), minute=int(pref["local_minute"]), second=0, microsecond=0)
    delta = (local_now - target).total_seconds() / 60
    return 0 <= delta <= MAX_CATCHUP_MINUTES, local_now.date().isoformat(), target


def _events_for_digest(conn, account_id: str, window_start_utc: datetime, limit: int = 10) -> list[dict]:
    ensure_lifecycle_table(conn)
    rows = conn.execute(
        f"""SELECT e.id AS event_id,e.score,e.created_at,t.id,t.title,t.source,t.external_id,t.deadline
            FROM opportunity_events e
            JOIN tenders t ON t.id=e.tender_id
            LEFT JOIN opportunity_lifecycle lc ON lc.source=t.source AND lc.external_id=t.external_id
            WHERE e.account_id=? AND e.event_type='new_high_match' AND e.created_at>=?
              AND {actionable_predicate('lc', 't')}
            ORDER BY e.score DESC,e.created_at DESC LIMIT ?""",
        (str(account_id), window_start_utc.isoformat(), int(limit)),
    ).fetchall()
    return [dict(row) for row in rows]


def _expo_send(tokens: list[str], *, title: str, body: str, data: dict) -> tuple[list[str], dict[str, str]]:
    if not tokens:
        return [], {}
    messages = [{
        "to": token, "title": title, "body": body, "sound": "default", "priority": "high",
        "channelId": "opportunities", "data": data,
    } for token in tokens]
    headers = {"Accept": "application/json", "Content-Type": "application/json", "Accept-Encoding": "gzip, deflate"}
    access_token = (os.getenv("EXPO_ACCESS_TOKEN") or "").strip()
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    response = requests.post(EXPO_PUSH_URL, json=messages, headers=headers, timeout=15)
    response.raise_for_status()
    payload = response.json()
    tickets = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(tickets, list) or len(tickets) != len(tokens):
        raise RuntimeError("invalid_expo_push_response")
    accepted, permanent_failures = [], {}
    for token, ticket in zip(tokens, tickets):
        if isinstance(ticket, dict) and ticket.get("status") == "ok":
            accepted.append(token)
            continue
        details = ticket.get("details") if isinstance(ticket, dict) else {}
        code = details.get("error") if isinstance(details, dict) else None
        if code == "DeviceNotRegistered":
            permanent_failures[token] = code
    return accepted, permanent_failures


def deliver_due_digests(*, now_utc: datetime | None = None, send_func=None) -> dict:
    now_utc = now_utc or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    send_func = send_func or _expo_send
    conn = _db()
    summary = {"accounts_due": 0, "sent": 0, "empty": 0, "failed": 0}
    try:
        ensure_push_schema(conn)
        prefs = conn.execute("SELECT p.* FROM push_preferences p JOIN accounts a ON a.account_id=p.account_id WHERE p.enabled=1 AND a.status='active' ORDER BY p.account_id").fetchall()
        for pref_row in prefs:
            pref = dict(pref_row)
            try:
                due, local_date, target_local = _due(pref, now_utc)
            except (ZoneInfoNotFoundError, ValueError):
                continue
            if not due:
                continue
            summary["accounts_due"] += 1
            existing = conn.execute(
                "SELECT status FROM push_digest_deliveries WHERE account_id=? AND local_date=?",
                (pref["account_id"], local_date),
            ).fetchone()
            if existing and existing["status"] == "sent":
                continue
            tokens = [row[0] for row in conn.execute(
                "SELECT token FROM push_devices WHERE account_id=? AND enabled=1 ORDER BY last_seen_at DESC",
                (pref["account_id"],),
            ).fetchall()]
            if not tokens:
                continue
            window_start_local = target_local - timedelta(days=1)
            window_start_utc = window_start_local.astimezone(timezone.utc)
            events = _events_for_digest(conn, pref["account_id"], window_start_utc)
            attempted_at = now_utc.isoformat()
            count = len(events)
            top = events[0] if events else None
            if top:
                top_title = str(top.get("title") or "Oportunidade relevante").strip()
                body = top_title[:150] if count == 1 else f"{count} novas oportunidades relevantes. Melhor correspondência: {top_title[:95]}"
            else:
                body = "Sem novas oportunidades de alta relevância nas últimas 24 horas."
            try:
                accepted, permanent_failures = send_func(
                    tokens,
                    title="ObraSignal · Radar da manhã",
                    body=body,
                    data={"type": "morning_digest", "opportunityId": top.get("id") if top else None, "count": count, "localDate": local_date},
                )
                for token in permanent_failures:
                    conn.execute("UPDATE push_devices SET enabled=0 WHERE token=?", (token,))
                if not accepted:
                    raise RuntimeError("no_push_device_accepted")
                conn.execute(
                    """INSERT INTO push_digest_deliveries(account_id,local_date,status,event_count,attempted_at,sent_at,error)
                       VALUES(?,?, 'sent',?,?,?,NULL)
                       ON CONFLICT(account_id,local_date) DO UPDATE SET status='sent',event_count=excluded.event_count,
                         attempted_at=excluded.attempted_at,sent_at=excluded.sent_at,error=NULL""",
                    (pref["account_id"], local_date, count, attempted_at, attempted_at),
                )
                conn.commit(); summary["sent"] += 1
            except Exception as exc:
                conn.execute(
                    """INSERT INTO push_digest_deliveries(account_id,local_date,status,event_count,attempted_at,error)
                       VALUES(?,?, 'failed',?,?,?)
                       ON CONFLICT(account_id,local_date) DO UPDATE SET status='failed',event_count=excluded.event_count,
                         attempted_at=excluded.attempted_at,error=excluded.error""",
                    (pref["account_id"], local_date, count, attempted_at, str(exc)[:500]),
                )
                conn.commit(); summary["failed"] += 1
        return summary
    finally:
        conn.close()


def _scheduler() -> None:
    while True:
        try:
            deliver_due_digests()
        except Exception as exc:
            print("push scheduler error:", exc)
        time.sleep(max(30, int(os.getenv("OBRASIGNAL_PUSH_POLL_SECONDS", "60"))))


def start_push_scheduler() -> None:
    global _scheduler_started
    with _scheduler_lock:
        if _scheduler_started:
            return
        threading.Thread(target=_scheduler, name="obrasignal-push-scheduler", daemon=True).start()
        _scheduler_started = True
