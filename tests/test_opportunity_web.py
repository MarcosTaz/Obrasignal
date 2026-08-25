from opportunity_web import render_opportunity_detail


def test_opportunity_detail_uses_open_visual_language_and_escapes_fields():
    html = render_opportunity_detail(
        {
            "title": '<script>alert("x")</script>',
            "buyer": "Município",
            "source": "TED",
            "country": "PT",
            "score": 88,
            "value": "150000 EUR",
            "deadline": "2030-01-01",
            "url": "https://example.test/opportunity",
            "is_actionable": True,
        },
        {
            "status": "QUALIFIED",
            "reason": "Perfil e Economic Fit favoráveis",
            "score": 88,
            "rule_version": "economic-fit-v1",
            "decided_at": "2030-01-01T00:00:00+00:00",
            "lines": [
                {"label": "Perfil", "value": "88/100", "detail": "compatibilidade forte"},
                {"label": "Capacidade", "value": "evidência", "detail": "estruturas metálicas"},
            ],
        },
    )

    assert "<script>alert(\"x\")</script>" not in html
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in html
    assert "#f6f9fc" in html
    assert "status-qualified" in html
    assert "Porque esta oportunidade está aqui" in html


def test_opportunity_detail_preserves_unknown_score_instead_of_rendering_zero():
    html = render_opportunity_detail(
        {"title": "Sem avaliação", "score": 0, "is_actionable": True},
        {"status": "SEM DECISÃO", "reason": "Ainda sem avaliação", "score": None, "lines": []},
    )

    assert "Não avaliada" in html
    assert "0/100" not in html


def test_opportunity_detail_does_not_turn_unknown_actionability_into_active():
    html = render_opportunity_detail(
        {"title": "Estado desconhecido", "is_actionable": None, "url": "https://example.test/source"},
        {"status": "REVIEW", "reason": "Rever evidência", "score": 55, "lines": []},
    )

    assert "Estado atual não confirmado" in html
    assert "Os dados atuais não confirmam se esta oportunidade continua acionável." in html
    assert "Esta oportunidade já não está ativa" not in html


def test_opportunity_detail_does_not_create_fake_source_link():
    html = render_opportunity_detail(
        {"title": "Sem fonte", "source": None, "url": None, "is_actionable": True},
        {"status": "SEM DECISÃO", "score": None, "lines": []},
    )

    assert "Fonte não identificada" in html
    assert "Ligação à fonte não disponível nos dados atuais." in html
    assert 'href="#"' not in html
    assert "Abrir fonte →" not in html


def test_opportunity_detail_separates_compatibility_from_bid_decision():
    html = render_opportunity_detail(
        {"title": "Teste", "score": 99, "is_actionable": True},
        {"status": "QUALIFIED", "score": 73, "reason": "Compatibilidade forte", "lines": []},
    )

    assert "Compatibilidade" in html
    assert "73" in html
    assert "99/100" not in html
    assert "a decisão de concorrer é tua" in html


def test_opportunity_detail_preserves_real_zero_value():
    html = render_opportunity_detail(
        {"title": "Valor zero explícito", "value": 0, "is_actionable": True},
        {"status": "REVIEW", "score": 10, "lines": []},
    )

    assert '<div class="meta-value">0</div>' in html
