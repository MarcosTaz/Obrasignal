from radar_web import render_radar_page


def test_radar_page_shows_decision_summary():
    html = render_radar_page([{"source": "TED", "country": "PRT", "title": "Estrutura metálica", "buyer": "Município de Leiria", "url": "https://example.test", "decision_summary": {"status": "QUALIFIED", "reason": "cumpre perfil e regras económicas", "score": 88}}])
    assert "QUALIFIED" in html
    assert "cumpre perfil e regras económicas" in html
    assert "88/100" in html
    assert "Estrutura metálica" in html


def test_radar_page_shows_explainable_layers():
    html = render_radar_page([{"source": "TED", "country": "PRT", "title": "Estrutura metálica", "decision_summary": {"status": "QUALIFIED", "reason": "cumpre regras", "score": 91, "layers": [
        {"label": "Perfil", "kind": "score", "score": 86, "scale": 100, "detail": "compatibilidade com perfil"},
        {"label": "Lote", "kind": "score", "score": 78, "scale": 100, "detail": "lote LOT-1"},
        {"label": "Geografia", "kind": "score", "score": 5, "scale": 5, "detail": "cidade prioritária"},
        {"label": "Capacidade", "kind": "evidence", "score": None, "evidence_count": 2, "detail": "capacidades encontradas"},
        {"label": "Economic Fit", "kind": "score", "score": 100, "scale": 100, "detail": "valor dentro do intervalo"},
    ]}}])
    assert "Perfil" in html and "86/100" in html
    assert "Lote" in html and "78/100" in html
    assert "Geografia" in html and "5/5" in html
    assert "Capacidade" in html and "2 evidência(s)" in html
    assert "Economic Fit" in html and "100/100" in html


def test_radar_page_uses_open_future_visual_system():
    html = render_radar_page([])
    assert "#F5F8FC" in html
    assert "#FFFFFF" in html
    assert "#2166F3" in html
    assert "Um radar comercial que explica cada oportunidade através do perfil da empresa, lote, geografia, capacidade e Economic Fit." in html


def test_radar_page_has_explicit_empty_state():
    assert "Nenhuma oportunidade encontrada." in render_radar_page([])


def test_radar_page_escapes_opportunity_fields():
    html = render_radar_page([{"title": '<script>alert(1)</script>', "decision_summary": {"status": "SEM DECISÃO", "reason": "sem dados"}}])
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
