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


def _seed(database):
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


def test_large_company_pages_deterministically_through_more_than_api_cap(monkeypatch, tmp_path):
    database = tmp_path / 'company-c.db'
    _configure(monkeypatch, database)
    app.init_db()
    client = APP.test_client()
    assert client.post('/api/v1/profile', json={
        'name': 'Construtora Sintética C', 'activity': 'construção',
        'contract_interests': ['empreitadas'], 'coverage_mode': 'portugal',
        'countries': ['PRT'], 'economic_min_score': 0,
    }).status_code == 200
    _seed(database)

    payloads = [
        client.get(f'/api/v1/opportunities?source=OBRASIGNAL_SYNTHETIC_C&limit=100&offset={offset}').get_json()
        for offset in (0, 100, 200)
    ]
    ids = [[item['external_id'] for item in payload['items']] for payload in payloads]
    assert [len(page) for page in ids] == [100, 100, 5]
    assert ids[0] + ids[1] + ids[2] == [f'C-{index:04d}' for index in range(205)]
    assert set(ids[0]).isdisjoint(ids[1])
    assert set(ids[0]).isdisjoint(ids[2])
    assert set(ids[1]).isdisjoint(ids[2])
    assert payloads[0]['page'] == {'limit': 100, 'offset': 0, 'has_more': True, 'next_offset': 100}
    assert payloads[1]['page'] == {'limit': 100, 'offset': 100, 'has_more': True, 'next_offset': 200}
    assert payloads[2]['page'] == {'limit': 100, 'offset': 200, 'has_more': False, 'next_offset': None}


def test_pagination_preserves_filter_identity_across_pages(monkeypatch, tmp_path):
    database = tmp_path / 'company-c-filter.db'
    _configure(monkeypatch, database)
    app.init_db()
    _seed(database)
    client = APP.test_client()
    page = client.get('/api/v1/opportunities?source=OBRASIGNAL_SYNTHETIC_C&q=Empreitada&open=1&limit=17&offset=34')
    assert page.status_code == 200
    payload = page.get_json()
    assert payload['page'] == {'limit': 17, 'offset': 34, 'has_more': True, 'next_offset': 51}
    assert len(payload['items']) == 17
    assert all(item['source'] == 'OBRASIGNAL_SYNTHETIC_C' for item in payload['items'])


def test_offset_is_bounded_and_invalid_values_fail_closed(monkeypatch, tmp_path):
    database = tmp_path / 'company-c-invalid.db'
    _configure(monkeypatch, database)
    app.init_db()
    client = APP.test_client()
    for value in ('-1', 'not-an-int', '100001'):
        response = client.get(f'/api/v1/opportunities?offset={value}')
        assert response.status_code == 400
        assert response.get_json() == {'error': 'invalid_query_parameter', 'parameter': 'offset'}
