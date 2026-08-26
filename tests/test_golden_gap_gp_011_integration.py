from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "mobile" / "App.js").read_text(encoding="utf-8")
API = (ROOT / "mobile" / "src" / "api.js").read_text(encoding="utf-8")
BACKEND = (ROOT / "source_health.py").read_text(encoding="utf-8")


def test_public_source_health_contract_exists_without_parallel_truth():
    assert "sourceHealth:" in API
    assert "/source-health-contract" in API
    for state in ("fresh", "aging", "stale", "unknown", "degraded", "unavailable"):
        assert state in BACKEND
    assert "zero_market_claim_allowed" in BACKEND
    assert "market_absence_proven" in BACKEND


def test_radar_consumes_source_health_contract_for_customer_visible_freshness():
    # GAP-GP-011 cannot close while the client exposes a public source-health method
    # but never consumes it in the Radar journey.
    assert "api.sourceHealth(" in APP
    for state in ("aging", "stale", "degraded", "unavailable"):
        assert state in APP


def test_empty_state_is_driven_by_source_coverage_not_global_sync_only():
    # A global last_sync cannot establish per-source freshness/coverage.
    assert "source_coverage" in APP or "sourceHealth" in APP
    assert "zero_market_claim_allowed" in APP or "market_absence_proven" in APP
    assert "O estado de frescura por fonte ainda não está disponível." not in APP


def test_partial_stats_failure_remains_explicit():
    assert "Contagens guardadas; a atualização não pôde ser confirmada." in APP
    assert "Contagens temporariamente indisponíveis." in APP


def test_source_identity_is_not_fabricated_as_ted():
    assert "Fonte não identificada" in APP
    assert "source||'TED'" not in APP
    assert 'source || \'TED\'' not in APP


def test_zero_market_claim_is_forbidden_in_customer_copy():
    assert "Isto não prova ausência de oportunidades no mercado." in APP or "não prova ausência" in APP
