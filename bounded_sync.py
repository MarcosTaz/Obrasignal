"""Bounded-write replacement for the legacy source-ingestion transaction.

Network fetch and scoring happen without a database writer. Canonical tender
upserts are committed in short chunks so authenticated customer writes do not
wait behind a full market refresh. A sync run is marked complete only after all
chunks succeed; incomplete run rows remain auditable and are ignored by the
normal completed-run readers.
"""
from __future__ import annotations

from datetime import datetime, timezone

import app as _app

DEFAULT_WRITE_CHUNK = 100

_UPSERT = """INSERT INTO tenders(
    title,description,buyer,country,cpv,value,deadline,publication_date,url,score,
    last_seen,published_at,match_reason,priority_label,priority_class,market,
    source,external_id,first_seen
) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
ON CONFLICT(source,external_id) DO UPDATE SET
    title=excluded.title,
    description=excluded.description,
    buyer=excluded.buyer,
    country=excluded.country,
    cpv=excluded.cpv,
    value=excluded.value,
    deadline=excluded.deadline,
    publication_date=excluded.publication_date,
    url=excluded.url,
    score=excluded.score,
    last_seen=excluded.last_seen,
    published_at=excluded.published_at,
    match_reason=excluded.match_reason,
    priority_label=excluded.priority_label,
    priority_class=excluded.priority_class,
    market=excluded.market"""


def _prepare_rows():
    raw = _app.fetch_ted()
    rows = []
    for notice in raw:
        item = _app.normalize_ted(notice)
        if item.get("external_id"):
            rows.append(item)
    try:
        rows.extend(_app.fetch_base())
    except Exception:
        # Preserve the historical BASE-is-optional behaviour. Source-health
        # wrappers still record the failure independently.
        pass

    for item in rows:
        score, label, css_class, reason = _app.commercial_score(
            item.get("title", ""), item.get("description", ""),
            item.get("cpv", ""), item.get("deadline"),
        )
        item["score"] = score
        item["priority_label"] = label
        item["priority_class"] = css_class
        item["match_reason"] = reason
    return rows


def _values(item, seen):
    return (
        item.get("title"), item.get("description"), item.get("buyer"), item.get("country"),
        item.get("cpv"), item.get("value"), item.get("deadline"), item.get("publication_date"),
        item.get("url"), item.get("score"), seen, item.get("published_at"),
        item.get("match_reason"), item.get("priority_label"), item.get("priority_class"),
        item.get("market"), item.get("source"), item.get("external_id"), seen,
    )


def sync_once(*, write_chunk=DEFAULT_WRITE_CHUNK):
    started = datetime.now(timezone.utc).isoformat()
    rows = _prepare_rows()
    seen = datetime.now(timezone.utc).isoformat()
    chunk = max(1, int(write_chunk))
    conn = _app.db()
    run_id = None
    try:
        # Commit the run marker before tender writes. If a later chunk fails the
        # NULL finished_at row is explicit evidence of an incomplete attempt.
        cur = conn.execute(
            "INSERT INTO sync_runs(started_at,finished_at,found,new_items) VALUES(?,NULL,0,0)",
            (started,),
        )
        run_id = int(cur.lastrowid)
        conn.commit()

        previous = conn.execute(
            "SELECT finished_at FROM sync_runs WHERE id<? AND finished_at IS NOT NULL ORDER BY id DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        previous_finished = previous[0] if previous else None

        pending = 0
        for item in rows:
            conn.execute(_UPSERT, _values(item, seen))
            pending += 1
            if pending >= chunk:
                conn.commit()
                pending = 0
        if pending:
            conn.commit()

        if previous_finished:
            new_items = conn.execute(
                """SELECT COUNT(*) FROM tenders
                   WHERE last_seen=? AND julianday(first_seen)>julianday(?)
                     AND julianday(first_seen)<=julianday(?)""",
                (seen, previous_finished, seen),
            ).fetchone()[0]
        else:
            new_items = conn.execute(
                "SELECT COUNT(*) FROM tenders WHERE last_seen=? AND first_seen=?",
                (seen, seen),
            ).fetchone()[0]

        conn.execute(
            "UPDATE sync_runs SET finished_at=?,found=?,new_items=? WHERE id=?",
            (seen, len(rows), int(new_items), run_id),
        )
        conn.commit()
        return len(rows), int(new_items)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
