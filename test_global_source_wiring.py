import preload
from source_runtime import discard_staged_source_syncs, staged_source_syncs
from uruguay_arce_runtime import ARCERuntimeBatch


class FakeConn:
    def close(self):
        pass


def test_ready_global_sources_still_require_explicit_request(monkeypatch):
    monkeypatch.delenv('OBRASIGNAL_GLOBAL_SOURCES', raising=False)
    assert preload._global_source_enabled('CO_SECOP') is False
    assert preload._global_source_enabled('PY_DNCP') is False
    assert preload._global_source_enabled('UY_ARCE') is False

    monkeypatch.setenv('OBRASIGNAL_GLOBAL_SOURCES', 'CO_SECOP,PY_DNCP,UY_ARCE')
    assert preload._global_source_enabled('CO_SECOP') is True
    assert preload._global_source_enabled('PY_DNCP') is True
    assert preload._global_source_enabled('UY_ARCE') is True


def test_explicit_request_cannot_bypass_a_failing_production_gate(monkeypatch):
    monkeypatch.setenv('OBRASIGNAL_GLOBAL_SOURCES', 'CO_SECOP')
    monkeypatch.setattr(preload, 'production_gate_reasons', lambda source: ('commercial_reuse_not_green',))
    assert preload._global_source_enabled('CO_SECOP') is False


def test_secop_fetch_stages_cursor_instead_of_committing_it(monkeypatch):
    discard_staged_source_syncs()
    monkeypatch.setattr(preload._app, 'db', lambda: FakeConn())
    monkeypatch.setattr(preload, 'get_source_cursor', lambda conn, source: 'old-cursor')
    record = {'source': 'CO_SECOP', 'external_id': 'CO1.REQ.1', 'taxonomy': 'UNSPSC'}

    def fake_fetch(*, watermark=None):
        assert watermark == 'old-cursor'
        return [record], 'new-cursor'

    monkeypatch.setattr(preload._colombia_secop, 'fetch_secop_processes', fake_fetch)
    rows = preload._fetch_secop_staged()

    assert rows == [record]
    staged = staged_source_syncs()
    assert len(staged) == 1
    assert staged[0].source == 'CO_SECOP'
    assert staged[0].cursor == 'new-cursor'
    discard_staged_source_syncs()


def test_dncp_fetch_stages_cursor_instead_of_committing_it(monkeypatch):
    discard_staged_source_syncs()
    monkeypatch.setattr(preload._app, 'db', lambda: FakeConn())
    monkeypatch.setattr(preload, 'get_source_cursor', lambda conn, source: 'py-old')
    record = {'source': 'PY_DNCP', 'external_id': 'ocds-03ad3f-500001-1', 'taxonomy': 'DNCP'}

    def fake_fetch(*, watermark=None):
        assert watermark == 'py-old'
        return [record], 'py-new'

    monkeypatch.setattr(preload._paraguay_dncp, 'fetch_dncp_processes', fake_fetch)
    rows = preload._fetch_dncp_staged()

    assert rows == [record]
    staged = staged_source_syncs()
    assert len(staged) == 1
    assert staged[0].source == 'PY_DNCP'
    assert staged[0].cursor == 'py-new'
    discard_staged_source_syncs()


def test_arce_fetch_stages_tender_and_pac_but_projects_only_tender_to_legacy(monkeypatch):
    discard_staged_source_syncs()
    monkeypatch.setattr(preload._app, 'db', lambda: FakeConn())
    monkeypatch.setattr(preload, 'get_source_cursor', lambda conn, source: 'uy-old')
    tender = {
        'source': 'UY_ARCE',
        'signal_type': 'TENDER',
        'external_id': 'ocds-yfs5dr-100',
        'taxonomy': 'UNSPSC',
    }
    plan = {
        'source': 'UY_ARCE',
        'signal_type': 'PROCUREMENT_PLAN',
        'external_id': 'pac:100',
        'taxonomy': 'ARCE_PAC_FAMILY',
    }

    def fake_batch(*, watermark=None):
        assert watermark == 'uy-old'
        return ARCERuntimeBatch(
            legacy_tenders=(tender,),
            signals=(tender, plan),
            cursor='uy-new',
        )

    monkeypatch.setattr(preload._uruguay_arce_runtime, 'fetch_arce_runtime_batch', fake_batch)
    rows = preload._fetch_arce_staged()

    assert rows == [tender]
    staged = staged_source_syncs()
    assert len(staged) == 1
    assert staged[0].source == 'UY_ARCE'
    assert staged[0].cursor == 'uy-new'
    assert staged[0].records == [tender, plan]
    discard_staged_source_syncs()


def test_empty_incremental_dncp_window_is_healthy_not_source_failure(monkeypatch):
    events = []
    monkeypatch.setenv('BASE_ACCESS_TOKEN', 'configured')
    monkeypatch.setenv('OBRASIGNAL_GLOBAL_SOURCES', 'PY_DNCP')
    monkeypatch.setattr(preload._app, 'db', lambda: FakeConn())
    monkeypatch.setattr(preload, '_original_fetch_base', lambda: [{'source': 'BASE', 'external_id': 'base-1'}])
    monkeypatch.setattr(preload._national_sources, 'fetch_boamp', lambda: [{'source': 'BOAMP', 'external_id': 'boamp-1'}])
    monkeypatch.setattr(preload._national_sources, 'fetch_placsp', lambda: [{'source': 'PLACSP', 'external_id': 'placsp-1'}])
    monkeypatch.setattr(preload._national_sources, 'LUXEMBOURG_RSS_URL', '')
    monkeypatch.setattr(preload, '_fetch_dncp_staged', lambda: [])
    monkeypatch.setattr(preload, 'dedupe_records', lambda rows: rows)
    monkeypatch.setattr(
        preload,
        'record_source_result',
        lambda conn, source, **kwargs: events.append((source, kwargs)),
    )

    rows = preload.fetch_base_with_national_sources()

    assert len(rows) == 3
    dncp = [payload for source, payload in events if source == 'PY_DNCP']
    assert len(dncp) == 1
    assert dncp[0]['success'] is True
    assert dncp[0]['found'] == 0


def test_empty_incremental_arce_window_is_healthy_not_source_failure(monkeypatch):
    events = []
    monkeypatch.setenv('BASE_ACCESS_TOKEN', 'configured')
    monkeypatch.setenv('OBRASIGNAL_GLOBAL_SOURCES', 'UY_ARCE')
    monkeypatch.setattr(preload._app, 'db', lambda: FakeConn())
    monkeypatch.setattr(preload, '_original_fetch_base', lambda: [{'source': 'BASE', 'external_id': 'base-1'}])
    monkeypatch.setattr(preload._national_sources, 'fetch_boamp', lambda: [{'source': 'BOAMP', 'external_id': 'boamp-1'}])
    monkeypatch.setattr(preload._national_sources, 'fetch_placsp', lambda: [{'source': 'PLACSP', 'external_id': 'placsp-1'}])
    monkeypatch.setattr(preload._national_sources, 'LUXEMBOURG_RSS_URL', '')
    monkeypatch.setattr(preload, '_fetch_arce_staged', lambda: [])
    monkeypatch.setattr(preload, 'dedupe_records', lambda rows: rows)
    monkeypatch.setattr(
        preload,
        'record_source_result',
        lambda conn, source, **kwargs: events.append((source, kwargs)),
    )

    rows = preload.fetch_base_with_national_sources()

    assert len(rows) == 3
    arce = [payload for source, payload in events if source == 'UY_ARCE']
    assert len(arce) == 1
    assert arce[0]['success'] is True
    assert arce[0]['found'] == 0


def test_sync_failure_discards_staged_global_cursor(monkeypatch):
    discard_staged_source_syncs()

    def failing_sync(*args, **kwargs):
        preload.stage_source_sync(
            'CO_SECOP',
            [{'source': 'CO_SECOP', 'external_id': 'CO1.REQ.fail'}],
            'must-not-commit',
        )
        raise RuntimeError('database write failed')

    monkeypatch.setattr(preload, '_original_sync_once', failing_sync)

    try:
        preload.sync_once_with_events()
    except RuntimeError as exc:
        assert str(exc) == 'database write failed'
    else:
        raise AssertionError('expected sync failure')

    assert staged_source_syncs() == []


def test_successful_sync_commits_runtime_before_decisions(monkeypatch):
    calls = []
    conn = FakeConn()
    monkeypatch.setattr(preload, '_original_sync_once', lambda *a, **k: (7, 2))
    monkeypatch.setattr(preload._app, 'db', lambda: conn)
    monkeypatch.setattr(preload, 'commit_staged_source_syncs', lambda c: calls.append('runtime') or {'sources': 1})
    monkeypatch.setattr(preload, '_record_account_decisions', lambda c: calls.append('decisions') or 7)
    monkeypatch.setattr(preload, '_record_account_events', lambda c: calls.append('events') or [])
    monkeypatch.setattr(preload, 'record_stage', lambda *a, **k: calls.append('metrics'))

    result = preload.sync_once_with_events()

    assert calls == ['runtime', 'decisions', 'events', 'metrics']
    assert result['sync'] == (7, 2)
    assert result['source_runtime'] == {'sources': 1}
    assert result['decisions'] == 7
