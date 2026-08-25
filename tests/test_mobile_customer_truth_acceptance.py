from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "mobile" / "App.js"
NOTIFICATIONS = ROOT / "mobile" / "src" / "notifications.js"


def _app_source():
    return APP.read_text(encoding="utf-8")


def _notification_source():
    return NOTIFICATIONS.read_text(encoding="utf-8")


def test_mobile_stats_never_present_missing_counts_as_measured_zero():
    source = _app_source()
    assert "<Text style={s.statValue}>{v??0}</Text>" not in source, (
        "BUG-GP-006: customer-visible Radar stats convert UNKNOWN/unavailable values "
        "to numeric zero. Missing evidence must remain UNKNOWN, not 0."
    )


def test_mobile_cards_never_present_missing_relevance_as_zero_score():
    source = _app_source()
    assert "const score=item.decision_score??item.score??0" not in source, (
        "BUG-GP-006: opportunity card converts an absent relevance score to 0/100. "
        "Unknown score must remain explicitly unknown/not scored."
    )


def test_mobile_detail_never_present_missing_relevance_as_zero_score():
    source = _app_source()
    assert "{current.decision_score??current.score??0}/100" not in source, (
        "BUG-GP-006: opportunity detail converts an absent relevance score to 0/100. "
        "Unknown score must remain explicitly unknown/not scored."
    )


def test_mobile_radar_refresh_failure_discloses_stale_cache_truth():
    source = _app_source()
    assert "Os resultados apresentados estão guardados e podem estar desactualizados." in source


def test_notification_permission_denial_is_not_encoded_as_zero_deliveries():
    source = _notification_source()
    assert "if (!granted) return 0;" not in source, (
        "BUG-GP-007: permission denied is collapsed into the same numeric result as "
        "permission granted with zero unread alerts. Denial must remain distinct."
    )


def test_mobile_never_claims_notifications_active_from_ambiguous_zero_result():
    source = _app_source()
    assert "delivered>0?`${delivered} alerta(s) novo(s).`:'Notificações activadas.'" not in source, (
        "BUG-GP-007: an ambiguous zero result is rendered as notifications active. "
        "OS permission denial must never be presented as success."
    )


def test_mobile_relevance_score_is_not_described_as_customer_recommendation():
    source = _app_source()
    assert "O scoring é uma recomendação baseada no perfil da tua empresa." not in source, (
        "BUG-GP-009: relevance/match scoring is presented as a recommendation. "
        "Ranking evidence must remain separate from the customer's explicit pursuit decision."
    )


def test_mobile_card_never_fabricates_ted_when_source_is_missing():
    source = _app_source()
    assert "item.source||'TED'" not in source, (
        "BUG-GP-010: absent source identity is fabricated as TED on opportunity cards. "
        "Missing provenance must remain unknown."
    )


def test_mobile_detail_never_fabricates_ted_when_source_is_missing():
    source = _app_source()
    assert "current.source||'TED'" not in source, (
        "BUG-GP-010: absent source identity is fabricated as TED on opportunity detail. "
        "Missing provenance must remain unknown."
    )


def test_radar_empty_state_does_not_attribute_unknown_market_state_to_filters():
    source = _app_source()
    assert "Sem resultados com estes filtros." not in source, (
        "GAP-GP-011: the empty state attributes an empty Radar to customer filters even "
        "though source freshness/coverage may be stale, degraded or unknown. The customer "
        "must be told only what the available evidence proves."
    )


def test_partial_stats_failure_is_not_silently_presented_as_current_state():
    source = _app_source()
    assert "const freshStats=statsResult.status==='fulfilled'?statsResult.value:stats;" not in source, (
        "GAP-GP-011: when stats refresh fails but opportunities succeeds, old/in-memory "
        "stats are silently retained with no partial-failure disclosure. Retained values "
        "must be marked stale/error or replaced by UNKNOWN."
    )


def test_radar_card_never_fabricates_positive_match_reason_when_reason_is_missing():
    source = _app_source()
    assert "item.decision_reason||item.match_reason||'Correspondência com o perfil'" not in source, (
        "BUG-GP-012: missing WHY evidence is replaced with a positive profile-match claim. "
        "No explanation evidence must remain unknown/unavailable, not become a fabricated reason."
    )
