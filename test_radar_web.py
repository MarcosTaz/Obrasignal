from radar_web import render_radar_page


def test_radar_page_shows_decision_summary():
    html = render_radar_page([
        {
            "source": "TED",
            "country": "PRT",
            "title": "Estrutura metálica",
            "buyer": "Município de Leiria",
            "url": "https://example.test",
            "decision_summary": {
                "status": "QUALIFIED",
                "reason": "cumpre perfil e regras económicas",
                "score": 88,
            },
        }
    ])

    assert "QUALIFIED" in html
    assert "cumpre perfil e regras económicas" in html
    assert "88/100" in html
    assert "Estrutura metálica" in html


def test_radar_page_has_explicit_empty_state():
    html = render_radar_page([])
    assert "Nenhuma oportunidade encontrada." in html


def test_radar_page_escapes_opportunity_fields():
    html = render_radar_page([
        {
            "title": '<script>alert(1)</script>',
            "decision_summary": {"status": "SEM DECISÃO", "reason": "sem dados"},
        }
    ])
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
