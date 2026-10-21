import sqlite3


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_scanner_detects_malformed_success_timestamp_that_current_main_snapshot_leaves_healthy():
    from data_integrity import scan_canonical_integrity
    from source_health import ensure_source_health, source_health_snapshot

    conn = _conn()
    ensure_source_health(conn)
    conn.execute(
        """INSERT INTO source_health
           (source,last_attempt,last_success,last_error,last_duration_ms,last_found,last_new_items,status)
           VALUES(?,?,?,?,?,?,?,?)""",
        ("TED", "2026-08-25T20:00:00+00:00", "not-a-time", None, 10, 1, 1, "healthy"),
    )
    conn.commit()

    snapshot = source_health_snapshot(conn)
    assert snapshot[0]["status"] == "healthy"
    assert snapshot[0]["age_minutes"] is None

    findings = scan_canonical_integrity(conn, exact_sha="66d43f6f")
    match = [item for item in findings if item.invariant == "SOURCE_HEALTH_TIMESTAMP_CORRUPT"]
    assert len(match) == 1
    assert match[0].severity == "HIGH"
    assert match[0].owner == "Source Health"
    assert match[0].repairable is True
    assert match[0].unknown is False
    conn.close()


def test_scanner_detects_source_health_success_after_last_attempt():
    from data_integrity import scan_canonical_integrity
    from source_health import ensure_source_health

    conn = _conn()
    ensure_source_health(conn)
    conn.execute(
        """INSERT INTO source_health
           (source,last_attempt,last_success,last_error,last_duration_ms,last_found,last_new_items,status)
           VALUES(?,?,?,?,?,?,?,?)""",
        (
            "TED",
            "2026-08-25T20:00:00+00:00",
            "2026-08-25T20:01:00+00:00",
            None,
            10,
            1,
            1,
            "healthy",
        ),
    )
    conn.commit()

    findings = scan_canonical_integrity(conn)
    match = [item for item in findings if item.invariant == "SOURCE_HEALTH_TIME_REGRESSION"]
    assert len(match) == 1
    assert match[0].severity == "HIGH"
    assert match[0].unknown is True
    conn.close()


def test_scanner_detects_invalid_duration_and_cursor_timestamp_without_mutation():
    from data_integrity import scan_canonical_integrity
    from source_health import ensure_source_health

    conn = _conn()
    ensure_source_health(conn)
    conn.execute(
        """INSERT INTO source_health
           (source,last_attempt,last_success,last_error,last_duration_ms,last_found,last_new_items,status)
           VALUES(?,?,?,?,?,?,?,?)""",
        (
            "TED",
            "2026-08-25T20:00:00+00:00",
            "2026-08-25T20:00:00+00:00",
            None,
            -1,
            1,
            1,
            "healthy",
        ),
    )
    conn.execute(
        "INSERT INTO source_cursor(source,watermark,updated_at) VALUES(?,?,?)",
        ("TED", "cursor-1", "2026-08-25 20:00:00"),
    )
    conn.commit()
    before = conn.total_changes
    conn.execute("PRAGMA query_only=ON")

    findings = scan_canonical_integrity(conn)
    invariants = {item.invariant for item in findings}
    assert "SOURCE_HEALTH_DURATION_INVALID" in invariants
    assert "SOURCE_CURSOR_TIMESTAMP_CORRUPT" in invariants
    assert conn.total_changes == before
    conn.close()
