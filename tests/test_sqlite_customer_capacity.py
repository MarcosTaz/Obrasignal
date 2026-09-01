import sqlite3
import time

from app import APP
import traffic_analytics as analytics
from traffic_analytics import ensure_traffic_schema, record_event


def _connection(path):
    conn = sqlite3.connect(path, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def test_analytics_never_waits_behind_real_wal_writer(tmp_path, monkeypatch):
    path = tmp_path / "capacity.db"
    setup = _connection(path)
    ensure_traffic_schema(setup)
    setup.close()

    writer = _connection(path)
    writer.execute("BEGIN IMMEDIATE")

    monkeypatch.setattr(analytics, "db", lambda: _connection(path))
    started = time.monotonic()
    try:
        with APP.test_request_context(
            "/api/v1/analytics/event",
            headers={"User-Agent": "Browser A", "Origin": "https://obrasignal.com"},
        ):
            assert record_event({"event": "page_view", "path": "/"}) is False
        elapsed = time.monotonic() - started
        # Product DB connections normally wait up to 15 seconds. Telemetry must
        # leave the customer request path far sooner when another writer exists.
        assert elapsed < 2.0
    finally:
        writer.rollback()
        writer.close()

    with APP.test_request_context(
        "/api/v1/analytics/event",
        headers={"User-Agent": "Browser A", "Origin": "https://obrasignal.com"},
    ):
        assert record_event({"event": "page_view", "path": "/"}) is True
