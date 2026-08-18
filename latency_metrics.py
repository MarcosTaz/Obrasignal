"""Pipeline latency telemetry for ObraSignal.

TED publication data exposes publication dates at day precision in the search
payload used by ObraSignal. We therefore do not pretend to measure an exact
publication-to-discovery timestamp. This module measures the parts we can
observe exactly: source fetch duration, pipeline processing duration and event
creation time, while retaining publication-date age separately when useful.
"""
from datetime import datetime, timezone


def ensure_latency_table(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS pipeline_latency(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            stage TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            duration_ms INTEGER NOT NULL,
            items INTEGER DEFAULT 0
        )"""
    )
    conn.commit()


def record_stage(conn, source, stage, started_at, duration_ms, items=0):
    ensure_latency_table(conn)
    finished = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO pipeline_latency(source,stage,started_at,finished_at,duration_ms,items) VALUES(?,?,?,?,?,?)",
        (source, stage, started_at, finished, int(duration_ms), int(items)),
    )
    conn.commit()


def latency_snapshot(conn, source=None, limit=100):
    ensure_latency_table(conn)
    if source:
        rows = conn.execute(
            "SELECT * FROM pipeline_latency WHERE source=? ORDER BY id DESC LIMIT ?",
            (source, int(limit)),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM pipeline_latency ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [dict(row) for row in rows]


def latency_summary(conn, source=None):
    ensure_latency_table(conn)
    where = "WHERE source=?" if source else ""
    params = (source,) if source else ()
    rows = conn.execute(
        f"SELECT stage, COUNT(*) AS samples, AVG(duration_ms) AS avg_ms, MAX(duration_ms) AS max_ms FROM pipeline_latency {where} GROUP BY stage ORDER BY stage",
        params,
    ).fetchall()
    return [
        {"stage": r[0], "samples": r[1], "avg_ms": round(r[2], 1), "max_ms": r[3]}
        for r in rows
    ]
