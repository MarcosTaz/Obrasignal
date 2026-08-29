from pathlib import Path


APP = Path("mobile/App.js")


def test_notification_permission_states_do_not_claim_activation_without_permission():
    app = APP.read_text(encoding="utf-8")

    assert "Platform.OS==='web'" in app
    assert "Notificações push requerem a aplicação nativa." in app
    assert "const granted=await configureNotifications()" in app
    assert "if(!granted)" in app
    assert "Notificações não activadas. Autoriza as notificações nas definições do dispositivo." in app
    assert "Não foi possível verificar as notificações. Tenta novamente mais tarde." in app


def test_radar_load_failure_does_not_render_empty_or_zero_value_state():
    app = APP.read_text(encoding="utf-8")

    assert "ListEmptyComponent={radarError?null:<Text style={s.empty}>" in app
    assert "Não baixes critérios só para criar resultados" in app
