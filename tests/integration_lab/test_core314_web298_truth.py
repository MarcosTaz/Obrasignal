from pathlib import Path

from decision_presentation import _feature_lines
from opportunity_web import render_opportunity_detail


def test_unknown_capability_evidence_count_is_not_zero():
    lines = _feature_lines({"capability_evidence": {"reason": None}})
    capability = next(line for line in lines if line["label"] == "Capacidade")
    assert capability["value"] == "Não indicado"
    assert "contagem de evidência não indicada" in capability["detail"]


def test_web_detail_preserves_q080_evidence_and_unknown_customer_truth():
    html = render_opportunity_detail(
        {
            "title": "Obra",
            "buyer": "Comprador",
            "source": None,
            "country": None,
            "score": None,
            "value": None,
            "deadline": None,
            "url": "javascript:alert(1)",
            "is_actionable": None,
        },
        {
            "status": "REVIEW",
            "score": None,
            "reason": "Compatibilidade por confirmar",
            "lines": [],
            "evidence": {
                "state": "READY",
                "confidence": "UNKNOWN",
                "sources": [{"source": "Fonte A", "field_name": "title", "stale": None}],
                "missing": ["deadline"],
                "conflict_count": 1,
            },
        },
    )
    assert "Não avaliada" in html
    assert "Estado atual não confirmado" in html
    assert "Esta análise ajuda a ordenar e explicar a oportunidade; a decisão de concorrer é tua." in html
    assert "Evidência da decisão" in html
    assert "Fonte A" in html
    assert "atualidade por confirmar" in html
    assert "Falta confirmar" in html
    assert "conflito(s) de evidência por resolver" in html
    assert "Fonte não identificada" in html
    assert "Ligação à fonte não disponível ou inválida" in html
    assert "javascript:alert(1)" not in html


def test_mobile_evidence_and_web_bounded_claims_coexist():
    explanation = Path("mobile/components/OpportunityExplanation.js").read_text(encoding="utf-8")
    app = Path("mobile/App.js").read_text(encoding="utf-8")
    assert "EvidenceSummary" in explanation
    assert "A ausência não é apresentada como confirmação" in explanation
    assert "toneForFactor" not in explanation
    assert "Última sincronização global registada:" in app
    assert "Atualidade da cobertura não confirmada." in app
    assert "Isto não prova ausência de oportunidades no mercado." in app
    assert "A pontuação expressa compatibilidade com o perfil; não é uma recomendação para concorrer." in app
    assert "sourceKnown(current.source)?'Abrir fonte oficial e documentos':'Abrir ligação disponível'" in app
