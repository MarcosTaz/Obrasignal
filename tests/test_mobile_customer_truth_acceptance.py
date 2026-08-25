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
