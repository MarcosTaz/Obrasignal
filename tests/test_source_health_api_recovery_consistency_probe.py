"""Data-truth probe: public consumers must preserve source-health recovery authority."""
from datetime import datetime, timezone, timedelta
import sqlite3


def _setup_api(monkeypatch, tmp_path):
    import api
    from decision_log import ensure_decision_table

    class Identity:
        account_id = "company-source-health-recovery"
        authenticated = True

    db_path = tmp_path / "source-health-api-recovery.db"

    def connect():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(api, "configured_identity", lambda: Identity())
    monkeypatch.setattr(api._preload._app, "db", connect)

    conn = connect()
    conn.execute(
        """CREATE TABLE tenders(
            id INTEGER PRIMARY KEY,
            source TEXT,
            external_id TEXT,
            title TEXT,
            description TEXT,
            buyer TEXT,
            country TEXT,
            cpv TEXT,
            deadline TEXT,
            publication_date TEXT,
            first_seen TEXT,
            score INTEGER,
            market TEXT
        )"""
    )
    ensure_decision_table(conn)
    conn.execute("CREATE TABLE sync_runs(id INTEGER PRIMARY KEY, finished_at TEXT)")
    conn.execute("INSERT INTO sync_runs VALUES (1, '2026-08-29T09:00:00+00:00')")
    conn.commit()
    return api, conn


def test_missing_active_source_recovery_is_consistent_across_public_consumers(monkeypatch, tmp_path):
    api, conn = _setup_api(monkeypatch, tmp_path)
    try:
        from source_health import record_source_result

        observed = datetime.now(timezone.utc) - timedelta(minutes=5)
        record_source_result(
            conn,
            "TED",
            success=True,
            duration_ms=50,
            found=0,
            new_items=0,
            observed_at=observed,
        )

        client = api.APP.test_client()
        health_before = client.get("/api/v1/source-health-contract")
        opportunities_before = client.get("/api/v1/opportunities?market=ALL")
        stats_before = client.get("/api/v1/stats")
        assert health_before.status_code == 200
        assert opportunities_before.status_code == 200
        assert stats_before.status_code == 200

        health_before_body = health_before.get_json()
        opportunities_before_body = opportunities_before.get_json()
        stats_before_body = stats_before.get_json()

        assert health_before_body["summary"]["expected_source_count"] == 2
        assert health_before_body["summary"]["observed_expected_source_count"] == 1
        assert health_before_body["summary"]["coverage_status"] == "unknown"
        assert health_before_body["summary"]["all_expected_sources_current"] is False
        assert opportunities_before_body["source_coverage"] == health_before_body["summary"]
        assert stats_before_body["source_coverage"] == health_before_body["summary"]
        assert opportunities_before_body["empty_result"]["state"] == "coverage_unconfirmed"
        assert opportunities_before_body["empty_result"]["market_absence_proven"] is False
        assert opportunities_before_body["empty_result"]["zero_market_claim_allowed"] is False

        record_source_result(
            conn,
            "BASE",
            success=True,
            duration_ms=60,
            found=0,
            new_items=0,
            observed_at=datetime.now(timezone.utc) - timedelta(minutes=4),
        )

        health_after_body = client.get("/api/v1/source-health-contract").get_json()
        opportunities_after_body = client.get("/api/v1/opportunities?market=ALL").get_json()
        stats_after_body = client.get("/api/v1/stats").get_json()

        assert health_after_body["summary"]["expected_source_count"] == 2
        assert health_after_body["summary"]["observed_expected_source_count"] == 2
        assert health_after_body["summary"]["coverage_status"] == "current"
        assert health_after_body["summary"]["all_expected_sources_current"] is True
        assert opportunities_after_body["source_coverage"] == health_after_body["summary"]
        assert stats_after_body["source_coverage"] == health_after_body["summary"]
        assert opportunities_after_body["empty_result"]["state"] == "observed_empty_current"
        assert opportunities_after_body["empty_result"]["market_absence_proven"] is False
        assert opportunities_after_body["empty_result"]["zero_market_claim_allowed"] is False
        assert health_after_body["summary"]["market_absence_proven"] is False
        assert health_after_body["summary"]["zero_market_claim_allowed"] is False
    finally:
        conn.close()
