import sqlite3

from analytics_funnel import activation_funnel


def _db():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE accounts(
            account_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            evaluation_activated_at TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE company_profiles(
            account_id TEXT PRIMARY KEY,
            profile_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE evaluation_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            event_name TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            metadata_json TEXT,
            UNIQUE(account_id,event_name,occurred_at)
        )"""
    )
    return conn


def _stage(result, name):
    return next(stage for stage in result["stages"] if stage["stage"] == name)


def test_incomplete_instrumentation_is_not_reported_as_customer_dropoff():
    conn = _db()
    try:
        conn.execute(
            "INSERT INTO accounts(account_id,created_at) VALUES(?,?)",
            ("company-a", "2026-08-25T10:00:00+00:00"),
        )
        result = activation_funnel(conn)
        market = _stage(result, "market_readiness")
        shortlist = _stage(result, "first_shortlist")

        assert market["unknown_accounts"] == 1
        assert market["progression_rate"] is None
        assert market["dropoff_rate"] is None
        assert shortlist["unknown_accounts"] == 1
        assert shortlist["dropoff_rate"] is None
        assert "UNKNOWN is measurement debt" in result["interpretation"]
    finally:
        conn.close()


def test_observed_event_count_does_not_make_partial_contract_complete():
    conn = _db()
    try:
        conn.execute(
            "INSERT INTO accounts(account_id,created_at) VALUES(?,?)",
            ("company-a", "2026-08-25T10:00:00+00:00"),
        )
        conn.executemany(
            "INSERT INTO evaluation_events(account_id,event_name,occurred_at) VALUES(?,?,?)",
            [
                ("company-a", "profile_ready", "2026-08-25T10:05:00+00:00"),
                ("company-a", "market_data_available", "2026-08-25T10:06:00+00:00"),
                ("company-a", "first_shortlist_generated", "2026-08-25T10:07:00+00:00"),
            ],
        )
        result = activation_funnel(conn)
        market = _stage(result, "market_readiness")
        shortlist = _stage(result, "first_shortlist")

        assert market["observed_accounts"] == 1
        assert market["measurement_complete"] is False
        assert market["progression_rate"] is None
        assert shortlist["observed_accounts"] == 1
        assert shortlist["measurement_complete"] is False
        assert shortlist["progression_rate"] is None
    finally:
        conn.close()


def test_profile_snapshot_is_counted_as_partial_evidence_not_completion_event():
    conn = _db()
    try:
        conn.execute(
            "INSERT INTO accounts(account_id,created_at) VALUES(?,?)",
            ("company-a", "2026-08-25T10:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO company_profiles(account_id,profile_json,updated_at) VALUES(?,?,?)",
            ("company-a", "{}", "2026-08-25T10:05:00+00:00"),
        )
        result = activation_funnel(conn)
        profile = _stage(result, "profile_completion")
        assert profile["observed_accounts"] == 0
        assert profile["partial_evidence_accounts"] == 1
        assert profile["measurement_complete"] is False
        assert profile["dropoff_rate"] is None
    finally:
        conn.close()


def test_population_is_account_scoped_and_event_evidence_does_not_cross_tenants():
    conn = _db()
    try:
        conn.executemany(
            "INSERT INTO accounts(account_id,created_at) VALUES(?,?)",
            [
                ("company-a", "2026-08-25T10:00:00+00:00"),
                ("company-b", "2026-08-25T10:00:00+00:00"),
            ],
        )
        conn.execute(
            "INSERT INTO evaluation_events(account_id,event_name,occurred_at) VALUES(?,?,?)",
            ("company-b", "market_data_available", "2026-08-25T10:10:00+00:00"),
        )
        result = activation_funnel(conn)
        market = _stage(result, "market_readiness")
        assert result["population_accounts"] == 2
        assert market["observed_accounts"] == 1
        assert market["unknown_accounts"] == 1
        assert market["progression_rate"] is None
    finally:
        conn.close()
