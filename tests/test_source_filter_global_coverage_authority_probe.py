"""Data-truth probe: source filtering must not overclaim global active coverage authority."""
from datetime import datetime, timezone, timedelta
import sqlite3


def _setup_api(monkeypatch, tmp_path):
    import api
    from decision_log import ensure_decision_table

    class Identity:
        account_id = "company-source-filter-global-coverage"
        authenticated = True

    db_path = tmp_path / "source-filter-global-coverage.db"

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


def test_source_filtered_opportunities_do_not_claim_global_active_coverage_current(monkeypatch, tmp_path):
    api, conn = _setup_api(monkeypatch, tmp_path)
    try:
        from source_health import record_source_result
        from source_registry import SOURCES

        active_sources = sorted(name for name, meta in SOURCES.items() if meta.get("status") == "active")
        assert "TED" in active_sources
        assert "BASE" in active_sources
        assert len(active_sources) >= 2

        # TED is current, while at least one other active source remains never-observed.
        record_source_result(
            conn,
            "TED",
            success=True,
            duration_ms=50,
            found=0,
            new_items=0,
            observed_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )

        client = api.APP.test_client()
        global_health = client.get("/api/v1/source-health-contract").get_json()
        filtered = client.get("/api/v1/opportunities?market=ALL&source=TED").get_json()

        assert global_health["summary"]["expected_source_count"] == len(active_sources)
        assert global_health["summary"]["all_expected_sources_current"] is False
        assert global_health["summary"]["coverage_status"] == "unknown"

        # A row filter must not silently weaken the authority represented by the
        # response field named source_coverage. Until the API exposes an explicit
        # requested-source scope alongside that summary, fail closed to global
        # active-source coverage rather than claiming all expected sources current.
        assert filtered["source_coverage"]["expected_source_count"] == len(active_sources)
        assert filtered["source_coverage"]["all_expected_sources_current"] is False
        assert filtered["source_coverage"]["coverage_status"] == "unknown"
        assert filtered["empty_result"]["state"] == "coverage_unconfirmed"
        assert filtered["empty_result"]["market_absence_proven"] is False
        assert filtered["empty_result"]["zero_market_claim_allowed"] is False
    finally:
        conn.close()
