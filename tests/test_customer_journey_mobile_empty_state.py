from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_empty_state_does_not_push_customer_to_lower_truth_thresholds():
    source = (ROOT / "mobile" / "App.js").read_text(encoding="utf-8")

    assert "Não há oportunidades nesta vista." in source
    assert "Isto pode dever-se aos filtros atuais ou a não existirem oportunidades que passem os critérios." in source
    assert "Não baixes critérios só para criar resultados" in source
    assert "ajusta-os apenas se a realidade comercial mudou" in source
    assert "Reduz a relevância mínima ou ajusta os critérios da empresa." not in source


def test_mobile_originating_workflow_controls_label_terminal_states_as_reported():
    source = (ROOT / "mobile" / "App.js").read_text(encoding="utf-8")

    assert "['WON','Ganho reportado']" in source
    assert "['LOST','Perdido reportado']" in source
    assert "['WON','Ganho']" not in source
    assert "['LOST','Perdido']" not in source
