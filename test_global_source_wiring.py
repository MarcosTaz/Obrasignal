import preload
from source_runtime import discard_staged_source_syncs, staged_source_syncs


class FakeConn:
    def close(self):
        pass


def test_ready_global_source_still_requires_explicit_request(monkeypatch):
    monkeypatch.delenv('OBRASIGNAL_GLOBAL_SOURCES', raising=False)
    assert preload._global_source_enabled('CO_SECOP') is False

    monkeypatch.setenv('OBRASIGNAL_GLOBAL_SOURCES', 'CO_SECOP')
    assert preload._global_source_enabled('CO_SECOP') is True


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
