from datetime import datetime, timezone, timedelta
import sqlite3


def _setup_api(monkeypatch, tmp_path):
    import api
    from decision_log import ensure_decision_table

    class Identity:
        account_id = "company-source-health"
        authenticated = True

    db_path = tmp_path / "source-health-api.db"

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
    # Source-health API acceptance must exercise the current decision contract,
    # not a historical five-column fixture that bypasses rule/profile authority.
    ensure_decision_table(conn)
    conn.execute("CREATE TABLE sync_runs(id INTEGER PRIMARY KEY, finished_at TEXT)")
    conn.execute("INSERT INTO sync_runs VALUES (1, '2026-08-25T10:00:00+00:00')")
    conn.commit()
    return api, connect, conn


def test_source_health_endpoint_exposes_source_specific_freshness_and_health(monkeypatch, tmp_path):
    api, connect, conn = _setup_api(monkeypatch, tmp_path)
    try:
        from source_health import record_source_result

        observed = datetime.now(timezone.utc) - timedelta(minutes=5)
        record_source_result(conn, 'TED', success=True, duration_ms=120, found=4, new_items=1, observed_at=observed)

        response = api.APP.test_client().get('/api/v1/source-health-contract?source=TED')
        assert response.status_code == 200
        body = response.get_json()
        assert body['contract_version'] == 'source-health-v1'
        assert body['account_id'] == 'company-source-health'
        assert len(body['items']) == 1
        item = body['items'][0]
        assert item['source'] == 'TED'
        assert item['freshness'] == 'fresh'
        assert item['health'] == 'healthy'
        assert item['stats_state'] == 'current'
        assert body['summary']['all_expected_sources_current'] is True
        assert body['summary']['market_absence_proven'] is False
    finally:
        conn.close()


def test_stale_empty_opportunity_response_is_coverage_unconfirmed_not_zero_market(monkeypatch, tmp_path):
    api, connect, conn = _setup_api(monkeypatch, tmp_path)
    try:
        from source_health import record_source_result

        stale = datetime.now(timezone.utc) - timedelta(hours=2)
        record_source_result(conn, 'TED', success=True, duration_ms=120, found=6, new_items=2, observed_at=stale)

        response = api.APP.test_client().get('/api/v1/opportunities?market=ALL&source=TED')
        assert response.status_code == 200
        body = response.get_json()
        assert body['items'] == []
        assert body['count'] == 0
        assert body['empty_result']['state'] == 'coverage_unconfirmed'
        assert body['empty_result']['coverage_status'] == 'degraded'
        assert body['empty_result']['market_absence_proven'] is False
        assert body['empty_result']['zero_market_claim_allowed'] is False
        assert body['source_health_contract_version'] == 'source-health-v1'
    finally:
        conn.close()


def test_stats_success_is_explicit_and_source_coverage_remains_separate(monkeypatch, tmp_path):
    api, connect, conn = _setup_api(monkeypatch, tmp_path)
    try:
        response = api.APP.test_client().get('/api/v1/stats')
        assert response.status_code == 200
        body = response.get_json()
        assert body['stats_state'] == 'current'
        assert body['source_health_contract_version'] == 'source-health-v1'
        assert body['source_coverage']['market_absence_proven'] is False
        assert body['source_coverage']['zero_market_claim_allowed'] is False
        assert body['source_coverage']['coverage_status'] in {'unknown', 'degraded', 'unavailable', 'aging', 'current'}
    finally:
        conn.close()
