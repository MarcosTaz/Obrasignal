import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace

from runtime_radar_integrity import canonical_ted_deadline, install
from source_health import ensure_source_health, get_source_cursor, set_source_cursor
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, staged_source_syncs


def _fake_runtime():
    return (
        SimpleNamespace(set_source_cursor=set_source_cursor),
        SimpleNamespace(normalize_ted=lambda _notice: {"deadline": "2026-09-05 | 2026-09-12"}),
    )


def test_canonical_ted_deadline_uses_latest_open_lot_date():
    notice = {
        "deadline-receipt-tender-date-lot": [
            {"eng": "2026-09-05"},
            "2026-09-12",
            "20260909",
        ]
    }
    assert canonical_ted_deadline(notice, "2026-09-05 | 2026-09-12") == "2026-09-12"


def test_ted_cursor_is_not_written_before_successful_staged_commit():
    discard_staged_source_syncs()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)

    fake_preload, fake_app = _fake_runtime()
    install(fake_preload, fake_app)

    fake_preload.set_source_cursor(conn, "TED", "20260903")
    assert get_source_cursor(conn, "TED") is None
    pending = staged_source_syncs()
    assert len(pending) == 1
    assert pending[0].source == "TED"
    assert pending[0].cursor == "20260903"

    # Simulated failure path: the sync wrapper discards pending source state.
    discard_staged_source_syncs()
    assert get_source_cursor(conn, "TED") is None

    # Success path: the cursor becomes durable only at the post-persistence
    # source-runtime commit boundary.
    fake_preload.set_source_cursor(conn, "TED", "20260903")
    result = commit_staged_source_syncs(conn)
    assert result["cursors"] == 1
    assert get_source_cursor(conn, "TED") == "20260903"
    conn.close()
    discard_staged_source_syncs()


def test_installed_normalizer_replaces_pipe_joined_lot_deadlines():
    fake_preload, fake_app = _fake_runtime()
    install(fake_preload, fake_app)
    normalized = fake_app.normalize_ted({
        "deadline-receipt-tender-date-lot": ["2026-09-05", "2026-09-12"]
    })
    assert normalized["deadline"] == "2026-09-12"


def test_date_only_deadline_today_is_urgent_and_open():
    import api

    fake_preload, fake_app = _fake_runtime()
    install(fake_preload, fake_app)
    today = datetime.now(timezone.utc).date().isoformat()
    state = api._deadline_state(today)
    assert state["state"] == "urgent"
    assert state["days_remaining"] == 0
    item = api._row({"deadline": today})
    assert item["is_actionable"] is True
    assert item["is_open"] is True
