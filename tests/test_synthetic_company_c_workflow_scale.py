import sqlite3

from opportunity_workflow import ensure_workflow_table, list_saved_opportunities, workflow_counts


def _db():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE tenders (
        id INTEGER PRIMARY KEY,
        source TEXT NOT NULL,
        external_id TEXT NOT NULL,
        title TEXT,
        buyer TEXT,
        country TEXT,
        deadline TEXT,
        url TEXT,
        score INTEGER,
        market TEXT,
        first_seen TEXT,
        last_seen TEXT,
        UNIQUE(source, external_id)
    )''')
    return conn


def _seed(conn, account_id, count=240, *, id_offset=0):
    ensure_workflow_table(conn)
    statuses = ('NEW', 'REVIEWING', 'PREPARING', 'SUBMITTED', 'WON', 'LOST')
    priorities = ('LOW', 'NORMAL', 'HIGH')
    for index in range(count):
        opportunity_id = id_offset + index + 1
        external_id = f'C-{opportunity_id:05d}'
        conn.execute(
            '''INSERT INTO tenders(id, source, external_id, title, buyer, country, deadline, url, score, market, first_seen, last_seen)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
            (opportunity_id, 'SYNTHETIC_C', external_id, f'Opportunity {opportunity_id}', 'Buyer C', 'PRT',
             f'2099-12-{(index % 28) + 1:02d}T23:59:00+00:00', f'https://example.invalid/{external_id}',
             50 + (index % 50), 'PT', '2026-08-30T00:00:00+00:00', '2026-08-30T00:00:00+00:00'),
        )
        conn.execute(
            '''INSERT INTO opportunity_workflow(account_id, source, external_id, status, note, priority, saved_at, updated_at)
               VALUES(?,?,?,?,?,?,?,?)''',
            (account_id, 'SYNTHETIC_C', external_id, statuses[index % len(statuses)], f'note-{index}',
             priorities[index % len(priorities)], f'2026-08-30T00:{index // 60:02d}:{index % 60:02d}+00:00',
             f'2026-08-30T00:{index // 60:02d}:{index % 60:02d}+00:00'),
        )
    conn.commit()


def test_company_c_watchlist_pages_large_corpus_without_overlap_or_tenant_leakage():
    conn = _db()
    _seed(conn, 'tenant-a', 240)
    _seed(conn, 'tenant-b', 20, id_offset=1000)

    pages = [list_saved_opportunities(conn, 'tenant-a', order='recent', limit=100, offset=offset) for offset in (0, 100, 200)]
    assert [len(page) for page in pages] == [100, 100, 40]

    ids = [item['opportunity_id'] for page in pages for item in page]
    assert len(ids) == 240
    assert len(set(ids)) == 240
    assert ids == sorted(ids, reverse=True)
    assert all(item['account_id'] == 'tenant-a' for page in pages for item in page)
    assert not any(item['opportunity_id'] >= 1001 for page in pages for item in page)


def test_company_c_workflow_counts_and_filters_remain_tenant_scoped_at_scale():
    conn = _db()
    _seed(conn, 'tenant-a', 240)
    _seed(conn, 'tenant-b', 24, id_offset=1000)

    counts = workflow_counts(conn, 'tenant-a')
    assert sum(counts.values()) == 240
    assert counts['NEW'] == 40
    assert counts['REVIEWING'] == 40
    assert counts['PREPARING'] == 40
    assert counts['SUBMITTED'] == 40
    assert counts['WON'] == 40
    assert counts['LOST'] == 40

    high = list_saved_opportunities(conn, 'tenant-a', priority='HIGH', order='priority', limit=100, offset=0)
    reviewing = list_saved_opportunities(conn, 'tenant-a', status='REVIEWING', order='recent', limit=100, offset=0)
    assert len(high) == 80
    assert len(reviewing) == 40
    assert all(item['priority'] == 'HIGH' and item['account_id'] == 'tenant-a' for item in high)
    assert all(item['status'] == 'REVIEWING' and item['account_id'] == 'tenant-a' for item in reviewing)


def test_company_c_deadline_order_is_stable_across_page_boundary():
    conn = _db()
    _seed(conn, 'tenant-a', 240)
    first = list_saved_opportunities(conn, 'tenant-a', order='deadline', limit=100, offset=0)
    second = list_saved_opportunities(conn, 'tenant-a', order='deadline', limit=100, offset=100)
    combined = first + second
    keys = [(item['deadline'], item['saved_at'], item['opportunity_id']) for item in combined]
    assert len({item['opportunity_id'] for item in combined}) == 200
    assert [key[0] for key in keys] == sorted(key[0] for key in keys)
