import sqlite3

from decision_log import ensure_decision_table, latest_decision
from funnel_integration import persist_and_classify


def test_persist_and_classify_records_auditable_decision():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)

    item = {
        'source': 'TED',
        'external_id': '2026-S-999',
        'score': 81,
        'deadline': '2026-08-30',
        'market': 'EU',
    }
    decision, reason = persist_and_classify(conn, item, True)

    assert decision in {'QUALIFIED', 'REVIEW', 'REJECT'}
    assert reason
    row = latest_decision(conn, 'TED', '2026-S-999')
    assert row['decision'] == decision
    assert row['rule_version'] == 'commercial-v2+lot-v1+capability-v1+economic-fit-v2'
    assert 'profile_score' in row['features']
    assert 'economic_fit' in row['features']
