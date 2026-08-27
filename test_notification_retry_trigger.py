"""Production wiring guard for notification retry/receipt processing."""
from pathlib import Path


def test_production_sync_dispatches_notification_work_for_every_active_account():
    """Retries must be server-driven even when the app is closed and no new event appears."""
    source = Path("preload.py").read_text(encoding="utf-8")

    assert "accounts = list_active_accounts(conn) or [configured_identity().account_id]" in source
    assert "record_new_opportunities(conn, account_id=account_id, min_score=75)" in source
    assert "events = _record_account_events(conn)" in source
    assert "_app.sync_once = sync_once_with_events" in source


def test_record_new_opportunities_processes_existing_receipts_and_pending_sends():
    """The per-account hook must do useful delivery work even when it inserts zero new events."""
    source = Path("notification_events.py").read_text(encoding="utf-8")

    record_fn = source.split("def record_new_opportunities", 1)[1].split("def _push_identity", 1)[0]
    assert "reconcile_push_receipts(conn, account_id)" in record_fn
    assert "submit_pending_pushes(conn, account_id)" in record_fn
