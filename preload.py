"""Production compatibility layer for ObraSignal.

The application owns TED retrieval, normalization, scoring and dashboard
behaviour directly. This module only augments synchronization with validated
national sources and records deduplicated high-value opportunity events.
"""
import app as _app
from national_sources import fetch_national_sources
from notification_events import record_new_opportunities

APP = _app.APP

_original_fetch_base = _app.fetch_base
_original_sync_once = getattr(_app, "sync_once", None)


def fetch_base_with_national_sources():
    """Keep Portugal BASE and add isolated national European connectors."""
    rows = _original_fetch_base()
    rows.extend(fetch_national_sources())
    return rows


_app.fetch_base = fetch_base_with_national_sources


def sync_once_with_events(*args, **kwargs):
    """Run the normal ingestion, then create one event per new high-score item."""
    if _original_sync_once is None:
        return None
    result = _original_sync_once(*args, **kwargs)
    conn = _app.db()
    try:
        events = record_new_opportunities(conn, min_score=75)
    finally:
        conn.close()
    return {"sync": result, "new_events": events}


# The background scheduler and manual sync both resolve this module-level name.
if _original_sync_once is not None:
    _app.sync_once = sync_once_with_events
