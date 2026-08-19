import sqlite3

from decision_log import ensure_decision_table, record_decision, latest_decision, funnel_counts


def test_decision_log_round_trip_and_funnel():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)

    record_decision(conn, 'TED', '2026-S-123', 'RELEVANT', 'CPV match', 82,
                    {'fit': 91, 'size': 74, 'deadline': 88}, decided_at='2026-08-18T18:00:00+00:00')
    record_decision(conn, 'TED', '2026-S-124', 'REJECTED', 'OUTSIDE_GEOGRAPHY', 21,
                    {'fit': 21}, decided_at='2026-08-18T18:01:00+00:00')
    record_decision(conn, 'TED', '2026-S-123', 'ALERTED', 'high score', 82,
                    {'fit': 91, 'size': 74, 'deadline': 88}, decided_at='2026-08-18T18:02:00+00:00')

    latest = latest_decision(conn, 'TED', '2026-S-123')
    assert latest['decision'] == 'ALERTED'
    assert latest['features']['fit'] == 91
    assert latest['rule_version'] == 'commercial-v1'

    counts = funnel_counts(conn)
    assert counts == {'ALERTED': 1, 'REJECTED': 1}
