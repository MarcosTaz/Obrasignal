from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "mobile" / "App.js").read_text(encoding="utf-8")


def test_unknown_stats_are_not_rendered_as_numeric_zero():
    assert "{v??0}" not in APP
    assert "metricText(v)" in APP
    assert "function metricText(value)" in APP


def test_missing_current_decision_score_is_not_zero_or_legacy_score():
    assert "item.decision_score??item.score??0" not in APP
    assert "current.decision_score??current.score??0" not in APP
    assert "const score=item.decision_score" in APP
    assert "scoreText(current.decision_score)" in APP
    assert "Não avaliada" in APP


def test_missing_decision_reason_is_not_fabricated_as_positive_profile_match():
    assert "item.decision_reason||item.match_reason||'Correspondência com o perfil'" not in APP
    assert "decisionReasonText(item)" in APP
    assert "Sem explicação de relevância disponível." in APP


def test_unknown_workflow_status_is_not_silently_new():
    assert "current.workflow?.status||'NEW'" not in APP
    assert "const status=current.workflow?.status??null" in APP
    assert "Estado atual não disponível. Escolhe explicitamente um estado antes de guardar." in APP
    assert "disabled={busy||!statusKnown}" in APP
    assert "if(!workflowStatusKnown(next))" in APP


def test_real_zero_and_explicit_user_state_transition_remain_supported():
    assert "isKnown(value)?String(value):'—'" in APP
    assert "STATES.map(([key,label])" in APP
    assert "onPress={()=>update(key)}" in APP
    assert "A pontuação expressa compatibilidade com o perfil; não é uma recomendação para concorrer." in APP
