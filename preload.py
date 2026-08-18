"""Production compatibility layer for ObraSignal.

The application owns TED retrieval, normalization, scoring and dashboard
behaviour directly. This module augments synchronization with validated
national sources, company-specific ranking and deduplicated opportunity events.
"""
import app as _app
from national_sources import fetch_national_sources
from notification_events import record_new_opportunities
from profile_scoring import personalized_score

APP = _app.APP
_original_fetch_base = _app.fetch_base
_original_sync_once = getattr(_app, "sync_once", None)


def fetch_base_with_national_sources():
    """Keep Portugal BASE and add isolated national European connectors."""
    rows = _original_fetch_base()
    rows.extend(fetch_national_sources())
    return rows


_app.fetch_base = fetch_base_with_national_sources


def _ensure_profile_columns(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(tenders)").fetchall()}
    if "global_score" not in cols:
        conn.execute("ALTER TABLE tenders ADD COLUMN global_score INTEGER")
    if "profile_score" not in cols:
        conn.execute("ALTER TABLE tenders ADD COLUMN profile_score INTEGER")
    if "profile_reason" not in cols:
        conn.execute("ALTER TABLE tenders ADD COLUMN profile_reason TEXT")
    conn.commit()


def _apply_profile_scores(conn):
    """Preserve the commercial score and derive the active profile score."""
    _ensure_profile_columns(conn)
    rows = conn.execute("SELECT * FROM tenders").fetchall()
    for row in rows:
        d = dict(row)
        base = int(d.get("global_score") if d.get("global_score") is not None else d.get("score") or 0)
        score, label, cls, reason = personalized_score(d, base)
        conn.execute(
            "UPDATE tenders SET global_score=?, profile_score=?, score=?, priority_label=?, priority_class=?, profile_reason=?, match_reason=? WHERE id=?",
            (base, score, score, label, cls, reason, reason, d["id"]),
        )
    conn.commit()


def sync_once_with_events(*args, **kwargs):
    """Run ingestion, personalize rankings, then record new high-value events."""
    if _original_sync_once is None:
        return None
    result = _original_sync_once(*args, **kwargs)
    conn = _app.db()
    try:
        _apply_profile_scores(conn)
        events = record_new_opportunities(conn, min_score=75)
    finally:
        conn.close()
    return {"sync": result, "new_events": events}


# The background scheduler and manual sync both resolve this module-level name.
if _original_sync_once is not None:
    _app.sync_once = sync_once_with_events
