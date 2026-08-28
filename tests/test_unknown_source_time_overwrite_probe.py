"""Failing-before probe: UNKNOWN publisher time must not overwrite known causal truth.

This is a data-truth boundary, not source business policy. Once durable source truth
has an explicit timezone-aware publisher timestamp, a later-arriving conflicting
observation whose publisher time is missing, malformed or timezone-naive has no
proven causal authority to replace that truth. Processing/arrival order must not
manufacture authority.
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


def test_unknown_publisher_time_cannot_overwrite_known_lifecycle_truth():
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
        authoritative = {
            "source": "TED",
            "external_id": "unknown-time-overwrite-1",
            "is_actionable": False,
            "lifecycle_status": "CLOSED",
            "lifecycle_reason": "publisher-closed",
            "source_updated_at": "2026-08-28T04:00:00+00:00",
            "_lifecycle_only": True,
        }
        stage_source_sync("TED", [authoritative], None)
        commit_staged_source_syncs(conn)
        before = _lifecycle(conn, authoritative["external_id"])

        variants = [
            ("missing", None),
            ("malformed", "not-a-time"),
            ("timezone-naive", "2026-08-28T05:00:00"),
        ]
        for label, unknown_time in variants:
            conflicting = dict(authoritative)
            conflicting.update(
                is_actionable=True,
                lifecycle_status="OPEN",
                lifecycle_reason=f"arrival-with-{label}-publisher-time",
                source_updated_at=unknown_time,
            )
            stage_source_sync("TED", [conflicting], None)
            commit_staged_source_syncs(conn)
            after = _lifecycle(conn, authoritative["external_id"])
            assert after == before, (
                f"{label} publisher time has UNKNOWN causal position relative to "
                "known durable publisher time; arrival order must not overwrite truth"
            )
    finally:
        discard_staged_source_syncs()
        conn.close()
