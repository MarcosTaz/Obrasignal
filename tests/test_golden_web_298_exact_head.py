from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "mobile" / "App.js").read_text(encoding="utf-8")
NOTIFICATIONS = (ROOT / "mobile" / "src" / "notifications.js").read_text(encoding="utf-8")


def test_bug_gp_006_unknown_is_not_zero_and_real_zero_remains_numeric():
    assert "const metricText=value=>isKnown(value)?String(value):'—';" in APP
    assert "const scoreText=value=>isKnown(value)?`${value}/100`:'Não avaliada';" in APP
    assert "const score=item.decision_score??item.score;" in APP
    assert "item.decision_score??item.score??0" not in APP
    assert "current.decision_score??current.score??0" not in APP
    assert "{v??0}" not in APP


def test_bug_gp_007_permission_denial_is_explicit_not_success():
    assert "return { status: 'permission_denied', delivered: 0 };" in NOTIFICATIONS
    assert "return { status: 'unsupported', delivered: 0 };" in NOTIFICATIONS
    assert "return { status: 'disabled', delivered: 0 };" in NOTIFICATIONS
    assert "return { status: 'ready', delivered };" in NOTIFICATIONS
    assert "Notificações não ativadas: permissão recusada no dispositivo." in APP
    assert "delivered>0?`${delivered} alerta(s) novo(s).`:'Notificações activadas.'" not in APP


def test_bug_gp_009_relevance_does_not_become_bid_recommendation():
    assert "O scoring é uma recomendação baseada no perfil da tua empresa." not in APP
    assert "recomendação" not in APP.lower() or "não é uma recomendação" in APP.lower()


def test_bug_gp_010_missing_source_never_fabricates_ted():
    assert "const sourceText=value=>typeof value==='string'&&value.trim()?value.trim():'Fonte não identificada';" in APP
    assert "item.source||'TED'" not in APP
    assert "current.source||'TED'" not in APP
    assert "referência não indicada" in APP
