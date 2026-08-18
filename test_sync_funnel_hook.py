import sqlite3

from decision_log import ensure_decision_table, funnel_counts
from sync_funnel_hook import record_sync_decisions


def test_record_sync_decisions_skips_unchanged_decision():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)
    rows = [
        {
            'source': 'TED', 'external_id': '2026-S-1', 'score': 80,
            'deadline': '2026-09-01', 'market': 'EU',
            'first_seen': '2026-08-18T10:00:00+00:00', 'last_seen': '2026-08-18T10:00:00+00:00',
            'match_reason': 'HIGH_COMMERCIAL_SCORE',
        }
    ]
    assert record_sync_decisions(conn, rows) == 1
    assert record_sync_decisions(conn, rows) == 0
    assert funnel_counts(conn)['RELEVANT'] == 1
