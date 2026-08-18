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
        },
        {
            "status": "QUALIFIED",
            "reason": "Perfil e Economic Fit favoráveis",
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
