import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app import APP
import traffic_analytics as analytics
from traffic_analytics import (
    _is_transient_sqlite_contention,
    _origin_allowed,
    ensure_traffic_schema,
    private_summary,
    record_event,
    visitor_day_hash,
)


ROOT = Path(__file__).resolve().parents[1]


def memory_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_traffic_schema_never_stores_raw_ip():
    conn = memory_db()
    ensure_traffic_schema(conn)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(traffic_events)")}
    assert "ip" not in columns
    assert "ip_address" not in columns
    assert "visitor_day_hash" in columns
    assert {"country", "region", "city", "timezone", "utm_source", "utm_campaign"} <= columns


def test_daily_visitor_hash_is_stable_but_rotates_by_day():
    conn = memory_db()
    ensure_traffic_schema(conn)
    a = visitor_day_hash(conn, ip="203.0.113.10", user_agent="Browser A", day="2026-08-31")
    b = visitor_day_hash(conn, ip="203.0.113.10", user_agent="Browser A", day="2026-08-31")
    c = visitor_day_hash(conn, ip="203.0.113.10", user_agent="Browser A", day="2026-09-01")
    assert a == b
    assert a != c
    assert len(a) == 32


def test_private_summary_counts_geo_campaign_and_funnel():
    conn = memory_db()
    ensure_traffic_schema(conn)
    rows = [
        ("2026-08-31T12:00:00+00:00","2026-08-31","2026-08-31T12:00","page_view","a","/","mail.example","email","outbound","pt_wave_1","PT","Leiria","Leiria","Europe/Lisbon","pt-PT","desktop","build"),
        ("2026-08-31T12:01:00+00:00","2026-08-31","2026-08-31T12:01","page_view","b","/","mail.example","email","outbound","pt_wave_1","PT","Lisboa","Lisboa","Europe/Lisbon","pt-PT","mobile","build"),
        ("2026-08-31T12:02:00+00:00","2026-08-31","2026-08-31T12:02","profile_completed","a","/","mail.example","email","outbound","pt_wave_1","PT","Leiria","Leiria","Europe/Lisbon","pt-PT","desktop","build"),
    ]
    conn.executemany(
        """INSERT INTO traffic_events(occurred_at,day,minute_bucket,event_name,visitor_day_hash,path,referrer_host,utm_source,utm_medium,utm_campaign,country,region,city,timezone,language,device,build_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()
    report = private_summary(conn, days=1, now=datetime(2026, 8, 31, 23, 59, tzinfo=timezone.utc))
    assert report["from"] == "2026-08-31"
    assert report["page_views"] == 2
    assert report["unique_visitors"] == 2
    assert report["campaigns"][0]["source"] == "email"
    assert any(row["country"] == "PT" for row in report["geography"])
    assert any(row["event_name"] == "profile_completed" for row in report["funnel"])


def test_private_analytics_accepts_only_configured_customer_origins(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_WEB_ORIGIN", "https://obrasignal.com")
    monkeypatch.setenv("OBRASIGNAL_CORS_FALLBACK_ORIGIN", "https://marcostaz.github.io")
    with APP.test_request_context("/api/v1/analytics/event", headers={"Origin": "https://obrasignal.com"}):
        assert _origin_allowed() is True
    with APP.test_request_context("/api/v1/analytics/event", headers={"Origin": "https://marcostaz.github.io"}):
        assert _origin_allowed() is True
    with APP.test_request_context("/api/v1/analytics/event", headers={"Origin": "https://attacker.example"}):
        assert _origin_allowed() is False


def test_contention_classifier_is_narrow():
    assert _is_transient_sqlite_contention(sqlite3.OperationalError("database is locked")) is True
    assert _is_transient_sqlite_contention(sqlite3.OperationalError("database schema is locked")) is True
    assert _is_transient_sqlite_contention(sqlite3.OperationalError("disk I/O error")) is False


class _FailingAnalyticsConnection:
    def __init__(self, message):
        self.message = message
        self.rolled_back = False
        self.closed = False

    def execute(self, statement, *_args, **_kwargs):
        if str(statement).startswith("PRAGMA busy_timeout="):
            return self
        raise sqlite3.OperationalError(self.message)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_telemetry_drops_transient_writer_contention_instead_of_raising(monkeypatch):
    conn = _FailingAnalyticsConnection("database is locked")
    monkeypatch.setattr(analytics, "db", lambda: conn)
    with APP.test_request_context("/api/v1/analytics/event", headers={"User-Agent": "Browser A"}):
        assert record_event({"event": "page_view", "path": "/"}) is False
    assert conn.rolled_back is True
    assert conn.closed is True


def test_telemetry_does_not_hide_non_contention_database_failures(monkeypatch):
    conn = _FailingAnalyticsConnection("disk I/O error")
    monkeypatch.setattr(analytics, "db", lambda: conn)
    with APP.test_request_context("/api/v1/analytics/event", headers={"User-Agent": "Browser A"}):
        with pytest.raises(sqlite3.OperationalError, match="disk I/O error"):
            record_event({"event": "page_view", "path": "/"})
    assert conn.rolled_back is True
    assert conn.closed is True


def test_customer_domain_is_canonical_in_production_configuration():
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    cors = (ROOT / "cors_app.py").read_text(encoding="utf-8")
    browser = (ROOT / ".github/workflows/browser-e2e.yml").read_text(encoding="utf-8")
    assert 'value: "https://obrasignal.com"' in render
    assert '"https://obrasignal.com"' in cors
    assert "https://obrasignal.com" in browser
