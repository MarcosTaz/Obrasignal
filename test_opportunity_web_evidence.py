from opportunity_web import render_opportunity_detail


def _item(url="https://example.test/tender"):
    return {
        "title": "Obra municipal",
        "buyer": "Município",
        "source": "TED",
        "country": "PRT",
        "score": 82,
        "value": "250000 EUR",
        "deadline": "2026-09-30",
        "url": url,
        "is_actionable": True,
    }


def _decision(evidence=None):
    return {
        "status": "QUALIFIED",
        "reason": "Compatível com o perfil",
        "rule_version": "commercial-v2",
        "decided_at": "2026-08-25T03:00:00+00:00",
        "lines": [{"label": "Perfil", "value": "82/100", "detail": "compatível"}],
        "evidence": evidence,
    }


def test_web_renders_redacted_evidence_without_private_graph_payload():
    evidence = {
        "state": "READY",
        "confidence": "MEDIUM",
        "sources": [
            {
                "source": "TED",
                "external_id": "2026-S-1",
                "field_name": "deadline",
                "stale": False,
            }
        ],
        "missing": ["source_freshness"],
        "conflict_count": 1,
    }
    html = render_opportunity_detail(_item(), _decision(evidence))

    assert "Evidência da decisão" in html
    assert "Confiança Média" in html
    assert "TED" in html
    assert "Prazo" in html
    assert "Atualidade da fonte" in html
    assert "1 conflito(s) de evidência" in html
    assert "company_profile.snapshot" not in html
    assert '"graph"' not in html


def test_web_fails_closed_on_unsafe_source_url():
    html = render_opportunity_detail(_item("javascript:alert(1)"), _decision())
    assert "javascript:alert" not in html
    assert "Ligação à fonte original indisponível ou inválida" in html
    assert 'href="javascript:' not in html


def test_web_escapes_untrusted_evidence_text():
    evidence = {
        "state": "READY",
        "confidence": "HIGH",
        "sources": [{"source": "<script>alert(1)</script>", "field_name": "title", "stale": False}],
        "missing": [],
        "conflict_count": 0,
    }
    html = render_opportunity_detail(_item(), _decision(evidence))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_web_states_unavailable_evidence_without_false_confirmation():
    html = render_opportunity_detail(
        _item(),
        _decision({"state": "UNAVAILABLE", "reason": "evidence_contract_rejected"}),
    )
    assert "Evidência da decisão indisponível" in html
    assert "A ausência de evidência não é apresentada como confirmação" in html
