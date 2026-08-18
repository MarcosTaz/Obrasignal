import sqlite3
import threading

from auth_context import get_account_id
from account_registry import list_active_accounts
from decision_log import latest_decision
from funnel_integration import persist_and_classify


def record_sync_decisions(conn, rows, account_id=None):
    """Record sync decisions under an explicit account or every active account."""
    accounts = [account_id] if account_id else list_active_accounts(conn)
    if not accounts:
        accounts = [get_account_id()]
    recorded = 0
    for current_account in accounts:
        for row in rows:
            item = dict(row)
            source = item.get('source', '')
            external_id = item.get('external_id', '')
            previous = latest_decision(conn, source, external_id, account_id=current_account)
            if previous and previous.get('score') == item.get('score') and previous.get('reason') == item.get('match_reason'):
                continue
            persist_and_classify(
                conn,
                item,
                item.get('first_seen') == item.get('last_seen'),
                account_id=current_account,
            )
            recorded += 1
    return recorded


def attach_to_app(app_module):
    original_sync = app_module.sync_once
    if getattr(original_sync, '_funnel_wrapped', False):
        return

    def wrapped_sync(*args, **kwargs):
        result = original_sync(*args, **kwargs)
        conn = app_module.db()
        try:
            run = conn.execute('SELECT finished_at FROM sync_runs ORDER BY id DESC LIMIT 1').fetchone()
            if run and run['finished_at']:
                rows = conn.execute('SELECT * FROM tenders WHERE last_seen=?', (run['finished_at'],)).fetchall()
                record_sync_decisions(conn, rows)
        finally:
            conn.close()
        return result

    wrapped_sync._funnel_wrapped = True
    app_module.sync_once = wrapped_sync


def install_thread_hook():
    original_start = threading.Thread.start
    if getattr(original_start, '_obrasignal_funnel_hook', False):
        return

    def start(thread, *args, **kwargs):
        target = getattr(thread, '_target', None)
        if getattr(target, '__name__', '') == 'worker':
            import app
            attach_to_app(app)
        return original_start(thread, *args, **kwargs)

    start._obrasignal_funnel_hook = True
    threading.Thread.start = start


install_thread_hook()
