"""Failing-before probe: equal publisher time with conflicting payload has no proven causal winner.

This is deliberately a data-truth probe, not owner policy. The current Temporal
contract explicitly refuses to invent ordering for equal source instants. If
repository behavior nevertheless overwrites canonical lifecycle truth on equal
publisher time, this test stays RED and routes the exact reproducer to the
Temporal/source owner rather than blessing arrival order as authority.
"""
import sqlite3


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_equal_source_time_conflicting_lifecycle_payload_does_not_choose_arrival_order():
    from opportunity_lifecycle import ensure_lifecycle_table
    from source_runtime import (
        commit_staged_source_syncs,
        discard_staged_source_syncs,
        stage_source_sync,
    )

    conn = _conn()
    discard_staged_source_syncs()
    try:
        ensure_lifecycle_table(conn)
        first = {
            "source": "TED",
            "external_id": "equal-time-1",
            "is_actionable": True,
            "lifecycle_status": "OPEN",
            "lifecycle_reason": "publisher-open",
            "source_updated_at": "2026-08-28T00:00:00+00:00",
            "_lifecycle_only": True,
        }
        conflicting = dict(first)
        conflicting.update(
            is_actionable=False,
            lifecycle_status="CLOSED",
            lifecycle_reason="publisher-closed",
        )

        # Exercise the real source staging/commit boundary twice at the exact
        # same publisher instant. Equal time proves neither observation newer.
        stage_source_sync("TED", [first], None)
        commit_staged_source_syncs(conn)
        before = dict(conn.execute(
            "SELECT is_actionable, lifecycle_status, lifecycle_reason, source_updated_at "
            "FROM opportunity_lifecycle WHERE source=? AND external_id=?",
            ("TED", "equal-time-1"),
        ).fetchone())

        stage_source_sync("TED", [conflicting], None)
        commit_staged_source_syncs(conn)
        after = dict(conn.execute(
            "SELECT is_actionable, lifecycle_status, lifecycle_reason, source_updated_at "
            "FROM opportunity_lifecycle WHERE source=? AND external_id=?",
            ("TED", "equal-time-1"),
        ).fetchone())

        assert after == before, (
            "equal explicit publisher timestamps do not establish causal order; "
            "arrival-order overwrite would invent authority"
        )
    finally:
        discard_staged_source_syncs()
        conn.close()
