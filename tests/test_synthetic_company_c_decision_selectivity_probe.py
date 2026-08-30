import sqlite3

from decision_log import ensure_decision_table


PAGE_INDEX = 'idx_opportunity_decisions_account_external_source_id'


def test_company_c_page_decision_lookup_uses_external_id_not_only_tenant_prefix():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)

    rows = []
    for opportunity in range(5000):
        external_id = f'C-{opportunity:05d}'
        for revision in range(4):
            rows.append(('tenant-a', 'SYNTHETIC_C', external_id, 'RELEVANT', 'reason', 80, '{}', 'commercial-v1', 'profile:test', 'opportunity:test', f'2026-08-30T00:00:{revision:02d}+00:00'))
    conn.executemany(
        '''INSERT INTO opportunity_decisions(account_id,source,external_id,decision,reason,score,features_json,rule_version,profile_fingerprint,opportunity_fingerprint,decided_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
        rows,
    )
    conn.commit()

    indexes = {row['name'] for row in conn.execute("PRAGMA index_list('opportunity_decisions')").fetchall()}
    assert PAGE_INDEX in indexes

    plan = conn.execute(
        '''EXPLAIN QUERY PLAN
           SELECT source, external_id, MAX(id) AS max_id
           FROM opportunity_decisions
           WHERE account_id=? AND external_id IN (?,?,?)
           GROUP BY source, external_id''',
        ('tenant-a', 'C-00010', 'C-02500', 'C-04999'),
    ).fetchall()
    detail = ' | '.join(str(row['detail']) for row in plan)
    assert PAGE_INDEX in detail
    assert 'account_id=? AND external_id=?' in detail
