"""Private, privacy-minimized traffic telemetry for obrasignal.com.

The collector intentionally has no customer-facing reporting route. It stores no
raw client IP and uses a server-side, persistent random HMAC key to derive a
rotating daily visitor identifier. Geography is limited to coarse edge-provided
headers when present plus browser timezone/language supplied by the Web client.

Telemetry is deliberately lower priority than customer traffic. SQLite permits
only one writer at a time, so analytics uses a very short writer wait and drops a
beacon on transient BUSY/LOCKED contention instead of consuming a customer HTTP
slot for seconds or surfacing an HTTP 500. Non-contention database failures still
raise: this is a bounded availability policy, not a blanket error suppressor.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from urllib.parse import urlsplit, urlunsplit

from flask import Blueprint, jsonify, request

from app import db

bp = Blueprint("traffic_analytics", __name__, url_prefix="/api/v1/analytics")

OFFICIAL_ORIGIN = "https://obrasignal.com"
PUBLISHED_FALLBACK_ORIGIN = "https://marcostaz.github.io"
ALLOWED_EVENTS = {
    "page_view",
    "authenticated_session",
    "profile_completed",
    "opportunity_opened",
    "checkout_opened",
    "checkout_completed",
}
BOT_RE = re.compile(
    r"bot|crawler|spider|slurp|headless|lighthouse|pagespeed|preview|github-actions|playwright|selenium",
    re.I,
)
MAX_TEXT = 160
ANALYTICS_BUSY_TIMEOUT_MS = 250

_TRAFFIC_READY_PROJECTION = """SELECT
    occurred_at,day,minute_bucket,event_name,visitor_day_hash,path,referrer_host,
    utm_source,utm_medium,utm_campaign,country,region,city,timezone,language,
    device,build_id FROM traffic_events LIMIT 0"""


def _traffic_schema_ready(conn):
    try:
        conn.execute("SELECT key,value,created_at FROM internal_config LIMIT 0")
        conn.execute(_TRAFFIC_READY_PROJECTION)
        return True
    except sqlite3.OperationalError:
        return False


def ensure_traffic_schema(conn):
    """Create/migrate telemetry storage only when it is actually absent."""
    if _traffic_schema_ready(conn):
        return
    conn.execute(
        """CREATE TABLE IF NOT EXISTS internal_config(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS traffic_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at TEXT NOT NULL,
            day TEXT NOT NULL,
            minute_bucket TEXT NOT NULL,
            event_name TEXT NOT NULL,
            visitor_day_hash TEXT NOT NULL,
            path TEXT NOT NULL,
            referrer_host TEXT,
            utm_source TEXT,
            utm_medium TEXT,
            utm_campaign TEXT,
            country TEXT,
            region TEXT,
            city TEXT,
            timezone TEXT,
            language TEXT,
            device TEXT,
            build_id TEXT,
            UNIQUE(visitor_day_hash, event_name, path, minute_bucket)
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_events_day ON traffic_events(day)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_events_campaign ON traffic_events(utm_source, utm_campaign)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_events_geo ON traffic_events(country, region, city)")
    conn.commit()


def _bounded(value, max_len=MAX_TEXT):
    if value is None:
        return None
    text = str(value).strip()
    return text[:max_len] if text else None


def _path(value):
    value = _bounded(value, 240) or "/"
    if not value.startswith("/"):
        value = "/"
    return value.split("?", 1)[0].split("#", 1)[0][:240]


def _referrer_host(value):
    value = _bounded(value, 500)
    if not value:
        return None
    try:
        return _bounded(urlsplit(value).hostname, 160)
    except Exception:
        return None


def _client_ip():
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
    return forwarded or (request.remote_addr or "unknown")


def _key(conn):
    row = conn.execute("SELECT value FROM internal_config WHERE key='traffic_hmac_key'").fetchone()
    if row:
        return bytes.fromhex(str(row[0]))
    value = secrets.token_hex(32)
    now = datetime.now(timezone.utc).isoformat()
    # INSERT OR IGNORE makes simultaneous first beacons converge on one key.
    conn.execute(
        "INSERT OR IGNORE INTO internal_config(key,value,created_at) VALUES(?,?,?)",
        ("traffic_hmac_key", value, now),
    )
    conn.commit()
    row = conn.execute("SELECT value FROM internal_config WHERE key='traffic_hmac_key'").fetchone()
    if not row:
        raise RuntimeError("traffic_hmac_key_not_persisted")
    return bytes.fromhex(str(row[0]))


def visitor_day_hash(conn, *, ip, user_agent, day):
    message = f"{day}|{ip}|{(user_agent or '')[:240]}".encode("utf-8", "ignore")
    return hmac.new(_key(conn), message, hashlib.sha256).hexdigest()[:32]


def _geo_from_headers():
    country = (
        request.headers.get("CF-IPCountry")
        or request.headers.get("X-Vercel-IP-Country")
        or request.headers.get("X-Geo-Country")
        or request.headers.get("X-AppEngine-Country")
    )
    region = request.headers.get("X-Vercel-IP-Country-Region") or request.headers.get("X-Geo-Region")
    city = request.headers.get("X-Vercel-IP-City") or request.headers.get("X-Geo-City")
    return _bounded(country, 8), _bounded(region, 80), _bounded(city, 80)


def _normalized_origin(value):
    value = str(value or "").strip()
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _allowed_origins():
    """Return only publisher-controlled customer Web origins."""
    canonical = _normalized_origin(os.getenv("OBRASIGNAL_WEB_ORIGIN") or OFFICIAL_ORIGIN)
    configured_fallback = _normalized_origin(os.getenv("OBRASIGNAL_CORS_FALLBACK_ORIGIN") or "")
    published_fallback = _normalized_origin(PUBLISHED_FALLBACK_ORIGIN)
    return {origin for origin in (canonical, configured_fallback, published_fallback) if origin}


def _origin_allowed():
    origin = _normalized_origin(request.headers.get("Origin") or "")
    mode = (os.getenv("OBRASIGNAL_AUTH_MODE") or "development").lower().strip()
    if not origin:
        return mode == "development"
    return origin in _allowed_origins()


def _is_bot():
    ua = request.headers.get("User-Agent") or ""
    synthetic = request.headers.get("X-ObraSignal-Synthetic") or ""
    return bool(BOT_RE.search(ua) or synthetic.lower() in {"1", "true", "yes"})


def _is_transient_sqlite_contention(exc):
    message = str(exc or "").lower()
    return any(marker in message for marker in (
        "database is locked",
        "database table is locked",
        "database schema is locked",
        "database is busy",
        "sqlite_busy",
        "sqlite_locked",
    ))


def record_event(payload):
    """Persist one telemetry event; return False only when contention drops it."""
    event_name = _bounded(payload.get("event"), 48)
    if event_name not in ALLOWED_EVENTS:
        raise ValueError("invalid_event")
    now = datetime.now(timezone.utc)
    day = now.date().isoformat()
    conn = db()
    try:
        # Override the product-wide 15s timeout for this non-critical write. A
        # telemetry beacon must never queue behind procurement ingestion.
        conn.execute(f"PRAGMA busy_timeout={ANALYTICS_BUSY_TIMEOUT_MS}")
        ensure_traffic_schema(conn)
        visitor = visitor_day_hash(
            conn,
            ip=_client_ip(),
            user_agent=request.headers.get("User-Agent") or "",
            day=day,
        )
        country, region, city = _geo_from_headers()
        values = (
            now.isoformat(),
            day,
            now.strftime("%Y-%m-%dT%H:%M"),
            event_name,
            visitor,
            _path(payload.get("path")),
            _referrer_host(payload.get("referrer")),
            _bounded(payload.get("utm_source"), 80),
            _bounded(payload.get("utm_medium"), 80),
            _bounded(payload.get("utm_campaign"), 120),
            country,
            region,
            city,
            _bounded(payload.get("timezone"), 80),
            _bounded(payload.get("language"), 32),
            _bounded(payload.get("device"), 32),
            _bounded(payload.get("build_id"), 80),
        )
        conn.execute(
            """INSERT OR IGNORE INTO traffic_events(
                occurred_at,day,minute_bucket,event_name,visitor_day_hash,path,
                referrer_host,utm_source,utm_medium,utm_campaign,country,region,
                city,timezone,language,device,build_id
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            values,
        )
        conn.commit()
        return True
    except sqlite3.OperationalError as exc:
        conn.rollback()
        if _is_transient_sqlite_contention(exc):
            return False
        raise
    finally:
        conn.close()


def private_summary(conn, *, days=30, now=None):
    ensure_traffic_schema(conn)
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    else:
        reference = reference.astimezone(timezone.utc)
    start = (reference.date() - timedelta(days=max(1, int(days)) - 1)).isoformat()
    totals = conn.execute(
        """SELECT COUNT(*) AS events,
                  COUNT(DISTINCT CASE WHEN event_name='page_view' THEN visitor_day_hash END) AS unique_visitors,
                  SUM(CASE WHEN event_name='page_view' THEN 1 ELSE 0 END) AS page_views
           FROM traffic_events WHERE day>=?""",
        (start,),
    ).fetchone()
    by_geo = conn.execute(
        """SELECT COALESCE(country,'UNKNOWN') country,
                  COALESCE(region,'') region, COALESCE(city,'') city,
                  COUNT(*) page_views,
                  COUNT(DISTINCT visitor_day_hash) unique_visitors
           FROM traffic_events WHERE day>=? AND event_name='page_view'
           GROUP BY country,region,city ORDER BY page_views DESC LIMIT 100""",
        (start,),
    ).fetchall()
    campaigns = conn.execute(
        """SELECT COALESCE(utm_source,'direct') source,
                  COALESCE(utm_campaign,'') campaign,
                  COUNT(*) page_views,
                  COUNT(DISTINCT visitor_day_hash) unique_visitors
           FROM traffic_events WHERE day>=? AND event_name='page_view'
           GROUP BY utm_source,utm_campaign ORDER BY page_views DESC LIMIT 100""",
        (start,),
    ).fetchall()
    funnel = conn.execute(
        """SELECT event_name, COUNT(*) events,
                  COUNT(DISTINCT visitor_day_hash) visitors
           FROM traffic_events WHERE day>=?
           GROUP BY event_name ORDER BY events DESC""",
        (start,),
    ).fetchall()
    return {
        "days": days,
        "from": start,
        "events": int(totals[0] or 0),
        "page_views": int(totals[2] or 0),
        "unique_visitors": int(totals[1] or 0),
        "geography": [dict(row) for row in by_geo],
        "campaigns": [dict(row) for row in campaigns],
        "funnel": [dict(row) for row in funnel],
    }


def purge_raw_events(conn, *, retain_days=90):
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=max(1, int(retain_days)))).isoformat()
    cur = conn.execute("DELETE FROM traffic_events WHERE day<?", (cutoff,))
    conn.commit()
    return int(cur.rowcount or 0)


@bp.route("/event", methods=["POST"])
def collect():
    if not _origin_allowed():
        return jsonify({"error": "origin_not_allowed"}), 403
    if _is_bot():
        return ("", 204)
    payload = request.get_json(silent=True) or {}
    try:
        record_event(payload)
    except ValueError:
        return jsonify({"error": "invalid_event"}), 400
    return ("", 204)
