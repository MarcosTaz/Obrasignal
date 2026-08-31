import sqlite3
from pathlib import Path

from traffic_analytics import (
    ensure_traffic_schema,
    private_summary,
    visitor_day_hash,
    visitor_period_hash,
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
    assert "visitor_period_hash" in columns
    assert {"country", "region", "city", "timezone", "utm_source", "utm_campaign"} <= columns


def test_daily_visitor_hash_rotates_but_monthly_hash_supports_returning_estimate():
    conn = memory_db()
    ensure_traffic_schema(conn)
    a = visitor_day_hash(conn, ip="203.0.113.10", user_agent="Browser A", day="2026-08-30")
    b = visitor_day_hash(conn, ip="203.0.113.10", user_agent="Browser A", day="2026-08-31")
    august_1 = visitor_period_hash(conn, ip="203.0.113.10", user_agent="Browser A", day="2026-08-30")
    august_2 = visitor_period_hash(conn, ip="203.0.113.10", user_agent="Browser A", day="2026-08-31")
    september = visitor_period_hash(conn, ip="203.0.113.10", user_agent="Browser A", day="2026-09-01")
    assert a != b
    assert august_1 == august_2
    assert august_1 != september
    assert len(a) == len(august_1) == 32


def test_private_summary_counts_geo_campaign_returning_and_funnel():
    conn = memory_db()
    ensure_traffic_schema(conn)
    rows = [
        ("2026-08-30T12:00:00+00:00","2026-08-30","2026-08-30T12:00","page_view","a-day1","a-month","/","mail.example","email","outbound","pt_wave_1","PT","Leiria","Leiria","Europe/Lisbon","pt-PT","desktop","build"),
        ("2026-08-31T12:00:00+00:00","2026-08-31","2026-08-31T12:00","page_view","a-day2","a-month","/","mail.example","email","outbound","pt_wave_1","PT","Leiria","Leiria","Europe/Lisbon","pt-PT","desktop","build"),
        ("2026-08-31T12:01:00+00:00","2026-08-31","2026-08-31T12:01","page_view","b-day","b-month","/","mail.example","email","outbound","pt_wave_1","PT","Lisboa","Lisboa","Europe/Lisbon","pt-PT","mobile","build"),
        ("2026-08-31T12:02:00+00:00","2026-08-31","2026-08-31T12:02","profile_completed","a-day2","a-month","/","mail.example","email","outbound","pt_wave_1","PT","Leiria","Leiria","Europe/Lisbon","pt-PT","desktop","build"),
    ]
    conn.executemany(
        """INSERT INTO traffic_events(occurred_at,day,minute_bucket,event_name,visitor_day_hash,visitor_period_hash,path,referrer_host,utm_source,utm_medium,utm_campaign,country,region,city,timezone,language,device,build_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()
    report = private_summary(conn, days=2)
    assert report["page_views"] == 3
    assert report["approximate_unique_visitors"] == 2
    assert report["returning_visitors"] == 1
    assert report["campaigns"][0]["source"] == "email"
    assert report["campaigns"][0]["medium"] == "outbound"
    assert any(row["country"] == "PT" for row in report["geography"])
    assert any(row["event_name"] == "profile_completed" for row in report["funnel"])
    assert len(report["daily"]) == 2


def test_customer_domain_is_canonical_in_production_configuration():
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    cors = (ROOT / "cors_app.py").read_text(encoding="utf-8")
    browser = (ROOT / ".github/workflows/browser-e2e.yml").read_text(encoding="utf-8")
    analytics = (ROOT / "traffic_analytics.py").read_text(encoding="utf-8")
    assert 'value: "https://obrasignal.com"' in render
    assert 'OFFICIAL_WEB_ORIGIN = "https://obrasignal.com"' in cors
    assert "https://obrasignal.com" in browser
    assert 'OFFICIAL_ORIGIN = "https://obrasignal.com"' in analytics
