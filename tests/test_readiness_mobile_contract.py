from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_api_exposes_readiness_as_authenticated_read():
    api = (ROOT / "mobile" / "src" / "api.js").read_text(encoding="utf-8")
    assert "readiness:(id)=>readWhenReady(`/opportunities/${encodeURIComponent(id)}/readiness`)" in api
    assert "writeWhenReady(`/opportunities/${encodeURIComponent(id)}/readiness`" not in api


def test_mobile_detail_renders_conservative_readiness_semantics():
    component = (ROOT / "mobile" / "components" / "OpportunityExplanation.js").read_text(encoding="utf-8")
    assert "Pronta para preparação" in component
    assert "Pronta com reservas" in component
    assert "Não pronta" in component
    assert "Por verificar" in component
    assert "Estado operacional, não decisão BID / NO-BID." in component
    assert "Por verificar” não significa bloqueado" in component


def test_mobile_readiness_status_uses_resolved_tone_variable():
    component = (ROOT / "mobile" / "components" / "OpportunityExplanation.js").read_text(encoding="utf-8")
    assert "{ color: tone }" in component
    assert "[styles.readinessStatus, { color }]" not in component


def test_mobile_readiness_does_not_render_completeness_as_score_or_gauge():
    component = (ROOT / "mobile" / "components" / "OpportunityExplanation.js").read_text(encoding="utf-8")
    lowered = component.lower()
    assert "data_completeness_percent" not in component
    assert "readiness score" not in lowered
    assert "gauge" not in lowered


def test_readiness_failure_is_locally_contained():
    component = (ROOT / "mobile" / "components" / "OpportunityExplanation.js").read_text(encoding="utf-8")
    assert "O resto do detalhe continua disponível." in component
    assert "Tentar novamente" in component
