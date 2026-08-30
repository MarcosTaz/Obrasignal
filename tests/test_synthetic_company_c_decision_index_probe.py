import sqlite3

from decision_log import ensure_decision_table


INDEX_NAME = 'idx_opportunity_decisions_account_source_external_id'


def test_company_c_latest_decision_query_has_tenant_scoped_covering_index():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)

    indexes = {row['name'] for row in conn.execute("PRAGMA index_list('opportunity_decisions')").fetchall()}
    assert INDEX_NAME in indexes

    rows = []
    for account in ('tenant-a', 'tenant-b'):
        for opportunity in range(1000):
            source = 'SYNTHETIC_C'
            external_id = f'C-{opportunity:05d}'
            for revision in range(3):
                rows.append((account, source, external_id, 'RELEVANT', 'reason', 80, '{}', 'commercial-v1', 'profile:test', 'opportunity:test', f'2026-08-30T00:00:{revision:02d}+00:00'))
    conn.executemany(
        '''INSERT INTO opportunity_decisions(account_id,source,external_id,decision,reason,score,features_json,rule_version,profile_fingerprint,opportunity_fingerprint,decided_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
        rows,
    )
    conn.commit()

    plan = conn.execute(
        '''EXPLAIN QUERY PLAN
           SELECT source, external_id, MAX(id) AS max_id
           FROM opportunity_decisions
           WHERE account_id=? AND external_id IN (?,?,?)
           GROUP BY source, external_id''',
        ('tenant-a', 'C-00010', 'C-00500', 'C-00999'),
    ).fetchall()
    detail = ' | '.join(str(row['detail']) for row in plan)
    assert INDEX_NAME in detail
    assert 'SCAN opportunity_decisions' not in detail
