from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "mobile" / "App.js").read_text(encoding="utf-8")
NOTIFICATIONS = (ROOT / "mobile" / "src" / "notifications.js").read_text(encoding="utf-8")


def test_bug_gp_006_unknown_is_not_zero_but_real_zero_remains_numeric():
    assert "const metricText=value=>isKnown(value)?String(value):'—';" in APP
    assert "const scoreText=value=>isKnown(value)?`${value}/100`:'Não avaliada';" in APP
    assert "v??0" not in APP
    assert "item.decision_score??item.score??0" not in APP
    assert "current.decision_score??current.score??0" not in APP


def test_bug_gp_007_permission_denial_is_distinct_from_ready_zero_delivery():
    assert "return { status: 'permission_denied', delivered: 0 };" in NOTIFICATIONS
    assert "return { status: 'ready', delivered };" in NOTIFICATIONS
    assert "Notificações não ativadas: permissão recusada no dispositivo." in APP
    assert "Sem novos alertas locais nesta verificação." in APP
    assert "Notificações activadas." not in APP


def test_bug_gp_009_relevance_is_not_bid_recommendation():
    assert "O scoring é uma recomendação baseada no perfil da tua empresa." not in APP
    assert "não é uma recomendação" in APP.lower()


def test_bug_gp_010_missing_source_is_not_fabricated_as_ted():
    assert "item.source||'TED'" not in APP
    assert "current.source||'TED'" not in APP
    assert "Fonte não identificada" in APP
    assert "referência não indicada" in APP


def test_bug_gp_012_missing_reason_remains_unavailable():
    assert "item.decision_reason||item.match_reason||'Correspondência com o perfil'" not in APP
    assert "Sem explicação de relevância disponível." in APP


def test_gap_gp_011_web_bounded_truth_is_explicit_but_not_source_specific():
    assert "Contagens guardadas; a atualização não pôde ser confirmada." in APP
    assert "Contagens temporariamente indisponíveis." in APP
    assert "Isto não prova ausência de oportunidades no mercado." in APP
    assert "A atualidade e cobertura das fontes não estão confirmadas." in APP
    assert "O estado de frescura por fonte ainda não está disponível." in APP
