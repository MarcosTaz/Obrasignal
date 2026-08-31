"""Current-spine failing-before for Source Health -> Radar customer truth.

Structural repository probe only. It proves whether the customer journey consumes
source coverage/freshness authority; it does not implement Source Health or Web/Mobile policy.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "mobile" / "App.js").read_text(encoding="utf-8")
API = (ROOT / "mobile" / "src" / "api.js").read_text(encoding="utf-8")
SOURCE_HEALTH = (ROOT / "source_health.py").read_text(encoding="utf-8")


def test_current_radar_has_a_public_source_health_consumer_boundary():
    # Internal source_health persistence/snapshots are not customer truth until the
    # client can consume a public account-safe contract.
    assert "source_health_snapshot" in SOURCE_HEALTH
    assert "sourceHealth:" in API or "/source-health" in API, (
        "SOURCE_HEALTH_NOT_EXPOSED_TO_RADAR: current client has no public Source Health read boundary"
    )
    assert "api.sourceHealth(" in APP, (
        "SOURCE_HEALTH_NOT_CONSUMED_BY_RADAR: Radar does not read source coverage/freshness authority"
    )


def test_unknown_source_identity_is_never_fabricated_as_ted():
    # Unknown provenance must remain unknown; a display convenience cannot invent TED.
    assert "item.source||'TED'" not in APP
    assert "current.source||'TED'" not in APP
    assert "Fonte não identificada" in APP or "Fonte desconhecida" in APP


def test_empty_radar_copy_does_not_claim_market_absence_without_coverage_authority():
    # Empty filtered results can be genuine, stale, partial or source-unavailable.
    # Until source coverage is consumed, copy must explicitly refuse the market-zero claim.
    assert "não prova ausência" in APP.lower() or "cobertura" in APP.lower(), (
        "ZERO_RESULTS_WITHOUT_COVERAGE_TRUTH: Radar empty state lacks an explicit coverage/absence caveat"
    )
    assert "Sem resultados com estes filtros." not in APP or "api.sourceHealth(" in APP
