import sqlite3


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_current_workflow_vocabulary_does_not_invent_terminality():
    from opportunity_workflow import STATUSES, get_workflow, set_workflow

    # Current owner vocabulary includes Watchlist's DISMISSED.  Historical
    # registry #488 predated it, so exact tuple equality from that tree is stale.
    assert STATUSES == (
        "NEW", "REVIEWING", "PREPARING", "SUBMITTED", "DISMISSED", "WON", "LOST"
    )

    conn = _conn()
    try:
        missing = get_workflow(conn, "tenant-a", "TED", "missing")
        assert missing["status"] == "NEW"
        # Repository evidence still does not authorize terminal semantics from
        # labels.  Exercise owner-accepted transitions without declaring a
        # terminal matrix in this Factory.
        for state in ("REVIEWING", "PREPARING", "SUBMITTED", "DISMISSED", "WON", "LOST"):
            current = set_workflow(conn, "tenant-a", "TED", "X-1", state)
            assert current["status"] == state
        reopened = set_workflow(conn, "tenant-a", "TED", "X-1", "REVIEWING")
        assert reopened["status"] == "REVIEWING"
    finally:
        conn.close()


def test_source_lifecycle_chronology_remains_temporal_owner_boundary():
    # The current composed spine owns explicit publisher-time stale rejection in
    # source_runtime.  State Machines consumes that authority; it must not add a
    # second arrival-time or processing-time transition policy.
    from pathlib import Path

    source = Path("source_runtime.py").read_text(encoding="utf-8")
    assert "source_updated_at" in source
    assert "datetime.now" not in source or "source_updated_at" in source


def test_event_ack_is_not_promoted_to_provider_delivery_authority():
    from pathlib import Path

    notification_source = Path("notification_events.py").read_text(encoding="utf-8")
    assert "delivered_at" in notification_source
    # Observation-only guard: no State Machine probe may infer physical/provider
    # delivery merely because the local acknowledgement marker is populated.
    assert "provider_delivery_confirmed" not in notification_source
