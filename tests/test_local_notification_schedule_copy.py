from pathlib import Path


def test_notification_notice_uses_scheduled_count_and_disclaims_delivery():
    app = Path('mobile/App.js').read_text(encoding='utf-8')
    start = app.index('function notificationSyncNotice')
    end = app.index('function sourceKnown', start)
    notice = app[start:end]
    assert 'result?.scheduled' in notice
    assert 'agendado(s)' in notice
    assert 'O agendamento não prova entrega.' in notice
    assert 'result?.delivered' not in notice
