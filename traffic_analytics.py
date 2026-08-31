"""Private, privacy-minimized traffic telemetry for obrasignal.com.

No analytics report is exposed to customers or the public Web application. The
collector never persists a raw IP address. It derives short-lived HMAC visitor
identifiers from network/address signals in memory, then discards those signals.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import re
import secrets
from urllib.parse import urlsplit

from flask import Blueprint, jsonify, request

from app import db

bp = Blueprint("traffic_analytics", __name__, url_prefix="/api/v1/analytics")

OFFICIAL_ORIGIN = "https://obrasignal.com"
LEGACY_ORIGIN = "https://marcostaz.github.io"
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


def ensure_traffic_schema(conn):
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
            visitor_period_hash TEXT,
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
    cols = {row[1] for row in conn.execute("PRAGMA table_info(traffic_events)").fetchall()}
    if "visitor_period_hash" not in cols:
        conn.execute("ALTER TABLE traffic_events ADD COLUMN visitor_period_hash TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_events_day ON traffic_events(day)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_events_period ON traffic_events(visitor_period_hash,day)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_events_campaign ON traffic_events(utm_source,utm_campaign)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_events_geo ON traffic_events(country,region,city)")
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
    conn.execute(
        "INSERT INTO internal_config(key,value,created_at) VALUES(?,?,?)",
        ("traffic_hmac_key", value, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return bytes.fromhex(value)


def _visitor_hash(conn, *, ip, user_agent, bucket):
    message = f"{bucket}|{ip}|{(user_agent or '')[:240]}".encode("utf-8", "ignore")
    return hmac.new(_key(conn), message, hashlib.sha256).hexdigest()[:32]


def visitor_day_hash(conn, *, ip, user_agent, day):
    return _visitor_hash(conn, ip=ip, user_agent=user_agent, bucket=f"day:{day}")


def visitor_period_hash(conn, *, ip, user_agent, day):
    # Monthly rotation gives useful new/returning estimates without a permanent
    # cross-month tracking identifier or client-side cookie/localStorage token.
    period = str(day)[:7]
    return _visitor_hash(conn, ip=ip, user_agent=user_agent, bucket=f"month:{period}")


def _geo_from_headers():
    # Use only coarse geography already supplied by trusted hosting/CDN edges.
    # Missing edge geography remains UNKNOWN; no third-party IP lookup is made.
    country = (
        request.headers.get("CF-IPCountry")
        or request.headers.get("X-Vercel-IP-Country")
        or request.headers.get("X-Geo-Country")
        or request.headers.get("X-AppEngine-Country")
    )
    region = request.headers.get("X-Vercel-IP-Country-Region") or request.headers.get("X-Geo-Region")
    city = request.headers.get("X-Vercel-IP-City") or request.headers.get("X-Geo-City")
    return _bounded(country, 8), _bounded(region, 80), _bounded(city, 80)


def _origin_allowed():
    origin = (request.headers.get("Origin") or "").strip().rstrip("/")
    mode = (os.getenv("OBRASIGNAL_AUTH_MODE") or "development").lower().strip()
    if not origin:
        return mode == "development"
    if mode == "provider":
        # Official customer traffic is always accepted even if the hosting
        # environment still carries the legacy CORS variable during cut-over.
        return origin in {OFFICIAL_ORIGIN, LEGACY_ORIGIN}
    configured = (os.getenv("OBRASIGNAL_WEB_ORIGIN") or OFFICIAL_ORIGIN).strip().rstrip("/")
    return origin == (configured or OFFICIAL_ORIGIN)


def _is_bot():
    ua = request.headers.get("User-Agent") or ""
    synthetic = request.headers.get("X-ObraSignal-Synthetic") or ""
    return bool(BOT_RE.search(ua) or synthetic.lower() in {"1", "true", "yes"})


def record_event(payload):
    event_name = _bounded(payload.get("event"), 48)
    if event_name not in ALLOWED_EVENTS:
        raise ValueError("invalid_event")
    now = datetime.now(timezone.utc)
    day = now.date().isoformat()
    conn = db()
    try:
        ensure_traffic_schema(conn)
        ip = _client_ip()
        user_agent = request.headers.get("User-Agent") or ""
        visitor_day = visitor_day_hash(conn, ip=ip, user_agent=user_agent, day=day)
        visitor_period = visitor_period_hash(conn, ip=ip, user_agent=user_agent, day=day)
        # Raw IP exists only in the local call frame above and is never written.
        country, region, city = _geo_from_headers()
        values = (
            now.isoformat(),
            day,
            now.strftime("%Y-%m-%dT%H:%M"),
            event_name,
            visitor_day,
            visitor_period,
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
                occurred_at,day,minute_bucket,event_name,visitor_day_hash,visitor_period_hash,path,
                referrer_host,utm_source,utm_medium,utm_campaign,country,region,
                city,timezone,language,device,build_id
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def private_summary(conn, *, days=30):
    ensure_traffic_schema(conn)
    days = max(1, int(days))
    start = (datetime.now(timezone.utc).date() - timedelta(days=days - 1)).isoformat()
    totals = conn.execute(
        """SELECT COUNT(*) AS events,
                  COUNT(DISTINCT CASE WHEN event_name='page_view' THEN visitor_day_hash END) AS unique_visitor_days,
                  COUNT(DISTINCT CASE WHEN event_name='page_view' THEN visitor_period_hash END) AS approximate_unique_visitors,
                  SUM(CASE WHEN event_name='page_view' THEN 1 ELSE 0 END) AS page_views
           FROM traffic_events WHERE day>=?""",
        (start,),
    ).fetchone()
    returning = conn.execute(
        """SELECT COUNT(*) FROM (
               SELECT visitor_period_hash FROM traffic_events
               WHERE day>=? AND event_name='page_view' AND visitor_period_hash IS NOT NULL
               GROUP BY visitor_period_hash HAVING COUNT(DISTINCT day)>1
           )""",
        (start,),
    ).fetchone()[0]
    by_geo = conn.execute(
        """SELECT COALESCE(country,'UNKNOWN') country,
                  COALESCE(region,'') region, COALESCE(city,'') city,
                  COALESCE(timezone,'') timezone,
                  COUNT(*) page_views,
                  COUNT(DISTINCT visitor_period_hash) unique_visitors
           FROM traffic_events WHERE day>=? AND event_name='page_view'
           GROUP BY country,region,city,timezone ORDER BY page_views DESC LIMIT 100""",
        (start,),
    ).fetchall()
    campaigns = conn.execute(
        """SELECT COALESCE(utm_source,'direct') source,
                  COALESCE(utm_medium,'') medium,
                  COALESCE(utm_campaign,'') campaign,
                  COUNT(*) page_views,
                  COUNT(DISTINCT visitor_period_hash) unique_visitors
           FROM traffic_events WHERE day>=? AND event_name='page_view'
           GROUP BY utm_source,utm_medium,utm_campaign ORDER BY page_views DESC LIMIT 100""",
        (start,),
    ).fetchall()
    referrers = conn.execute(
        """SELECT COALESCE(referrer_host,'direct') referrer,
                  COUNT(*) page_views,
                  COUNT(DISTINCT visitor_period_hash) unique_visitors
           FROM traffic_events WHERE day>=? AND event_name='page_view'
           GROUP BY referrer_host ORDER BY page_views DESC LIMIT 100""",
        (start,),
    ).fetchall()
    funnel = conn.execute(
        """SELECT event_name, COUNT(*) events,
                  COUNT(DISTINCT visitor_period_hash) visitors
           FROM traffic_events WHERE day>=?
           GROUP BY event_name ORDER BY events DESC""",
        (start,),
    ).fetchall()
    daily = conn.execute(
        """SELECT day,
                  SUM(CASE WHEN event_name='page_view' THEN 1 ELSE 0 END) page_views,
                  COUNT(DISTINCT CASE WHEN event_name='page_view' THEN visitor_day_hash END) unique_visitors
           FROM traffic_events WHERE day>=? GROUP BY day ORDER BY day""",
        (start,),
    ).fetchall()
    return {
        "days": days,
        "from": start,
        "events": int(totals[0] or 0),
        "unique_visitor_days": int(totals[1] or 0),
        "approximate_unique_visitors": int(totals[2] or 0),
        "page_views": int(totals[3] or 0),
        "returning_visitors": int(returning or 0),
        "geography": [dict(row) for row in by_geo],
        "campaigns": [dict(row) for row in campaigns],
        "referrers": [dict(row) for row in referrers],
        "funnel": [dict(row) for row in funnel],
        "daily": [dict(row) for row in daily],
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
