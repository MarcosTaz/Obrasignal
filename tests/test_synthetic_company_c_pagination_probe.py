import app
import account_registry
import opportunity_watchlist_api  # noqa: F401
from api import APP


def _configure(monkeypatch, database):
    monkeypatch.setattr(app, 'DB', str(database))
    monkeypatch.setenv('OBRASIGNAL_DB', str(database))
    monkeypatch.setenv('OBRASIGNAL_AUTH_MODE', 'development')
    monkeypatch.setenv('OBRASIGNAL_ACCOUNT_ID', 'synthetic-company-c')
    monkeypatch.setattr(
        account_registry,
        'subscription_state',
        lambda account: {'plan': 'pilot', 'active': True, 'source': 'synthetic-test', 'expires_at': None},
    )


def test_large_company_can_page_deterministically_through_more_than_api_cap(monkeypatch, tmp_path):
    database = tmp_path / 'company-c.db'
    _configure(monkeypatch, database)
    app.init_db()
    client = APP.test_client()
    assert client.post('/api/v1/profile', json={
        'name': 'Construtora Sintética C',
        'activity': 'construção',
        'contract_interests': ['empreitadas'],
        'coverage_mode': 'portugal',
        'countries': ['PRT'],
        'economic_min_score': 0,
    }).status_code == 200

    conn = app.db()
    try:
        rows = []
        for index in range(205):
            rows.append((
                'OBRASIGNAL_SYNTHETIC_C', f'C-{index:04d}', f'Empreitada {index:04d}',
                'Construção e reabilitação', 'Comprador Sintético', 'PRT', '45000000', None,
                '2099-12-31T23:59:00+00:00', '2026-08-29',
                f'https://example.invalid/c/{index:04d}', 0,
                '2026-08-29T00:00:00+00:00', '2026-08-29T00:00:00+00:00', 'PT',
            ))
        conn.executemany(
            '''INSERT INTO tenders(source,external_id,title,description,buyer,country,cpv,value,
               deadline,publication_date,url,score,first_seen,last_seen,market)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', rows,
        )
        conn.commit()
    finally:
        conn.close()

    first = client.get('/api/v1/opportunities?source=OBRASIGNAL_SYNTHETIC_C&limit=100&offset=0')
    second = client.get('/api/v1/opportunities?source=OBRASIGNAL_SYNTHETIC_C&limit=100&offset=100')
    third = client.get('/api/v1/opportunities?source=OBRASIGNAL_SYNTHETIC_C&limit=100&offset=200')
    assert first.status_code == second.status_code == third.status_code == 200

    p1, p2, p3 = first.get_json(), second.get_json(), third.get_json()
    ids1 = [item['external_id'] for item in p1['items']]
    ids2 = [item['external_id'] for item in p2['items']]
    ids3 = [item['external_id'] for item in p3['items']]
    assert len(ids1) == 100
    assert len(ids2) == 100
    assert len(ids3) == 5
    assert set(ids1).isdisjoint(ids2)
    assert set(ids1).isdisjoint(ids3)
    assert set(ids2).isdisjoint(ids3)
    assert ids1 + ids2 + ids3 == [f'C-{index:04d}' for index in range(205)]

    assert p1['page'] == {'limit': 100, 'offset': 0, 'has_more': True, 'next_offset': 100}
    assert p2['page'] == {'limit': 100, 'offset': 100, 'has_more': True, 'next_offset': 200}
    assert p3['page'] == {'limit': 100, 'offset': 200, 'has_more': False, 'next_offset': None}


def test_offset_is_bounded_and_invalid_values_fail_closed(monkeypatch, tmp_path):
    database = tmp_path / 'company-c-invalid.db'
    _configure(monkeypatch, database)
    app.init_db()
    client = APP.test_client()
    assert client.get('/api/v1/opportunities?offset=-1').status_code == 400
    assert client.get('/api/v1/opportunities?offset=not-an-int').status_code == 400
