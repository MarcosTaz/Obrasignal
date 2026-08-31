"""Failing-before probe: UNKNOWN↔UNKNOWN publisher time must not gain causal order from arrival.

This boundary is source-agnostic. If durable and incoming observations both lack a
provable timezone-aware publisher instant, their relative causal order is UNKNOWN.
A conflicting later arrival therefore must not silently replace durable lifecycle
truth merely because it was processed second.
"""
import sqlite3


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _lifecycle(conn, external_id):
    row = conn.execute(
        "SELECT is_actionable, lifecycle_status, lifecycle_reason, source_updated_at "
        "FROM opportunity_lifecycle WHERE source=? AND external_id=?",
        ("TED", external_id),
    ).fetchone()
    return dict(row) if row else None


def test_unknown_to_unknown_publisher_time_cannot_use_arrival_as_causal_authority():
    from opportunity_lifecycle import ensure_lifecycle_table
    from source_runtime import (
        commit_staged_source_syncs,
        discard_staged_source_syncs,
        stage_source_sync,
    )

    variants = [
        ("missing", None, "malformed", "not-a-time"),
        ("malformed", "not-a-time", "timezone-naive", "2026-08-28T08:00:00"),
        ("timezone-naive", "2026-08-28T07:00:00", "missing", None),
    ]

    for first_label, first_time, second_label, second_time in variants:
        conn = _conn()
        discard_staged_source_syncs()
        try:
            ensure_lifecycle_table(conn)
            external_id = f"unknown-unknown-{first_label}-{second_label}"
            first = {
                "source": "TED",
                "external_id": external_id,
                "is_actionable": False,
                "lifecycle_status": "CLOSED",
                "lifecycle_reason": f"first-{first_label}",
                "source_updated_at": first_time,
                "_lifecycle_only": True,
            }
            stage_source_sync("TED", [first], None)
            commit_staged_source_syncs(conn)
            before = _lifecycle(conn, external_id)

            conflicting = dict(first)
            conflicting.update(
                is_actionable=True,
                lifecycle_status="OPEN",
                lifecycle_reason=f"later-arrival-{second_label}",
                source_updated_at=second_time,
            )
            stage_source_sync("TED", [conflicting], None)
            commit_staged_source_syncs(conn)
            after = _lifecycle(conn, external_id)

            assert after == before, (
                f"{first_label}→{second_label} has UNKNOWN publisher chronology; "
                "later processing must not manufacture lifecycle authority"
            )
        finally:
            discard_staged_source_syncs()
            conn.close()
