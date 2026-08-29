from vertical_apps.industrial_claims.web import create_app


def test_operator_console_is_self_contained_and_exposes_full_assisted_journey(tmp_path):
    client = create_app(tmp_path / "console.sqlite3").test_client()
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "CausLedger" in html
    assert "Industrial Claims operator console" in html
    assert 'id="analyze-form"' in html
    assert 'id="review-form"' in html
    assert 'id="action-form"' in html
    assert 'id="resolve-form"' in html
    assert "Four-eyes review" in html
    assert "unknown notice deadline" in html.lower()
    assert "recovered net potential" not in html.lower()
    assert "guaranteed recovery" not in html.lower()
    assert "http://" not in html
    assert "https://" not in html


def test_console_shell_contains_no_tenant_or_case_data(tmp_path):
    client = create_app(tmp_path / "console.sqlite3").test_client()
    html = client.get("/").get_data(as_text=True)

    assert "alpha" not in html
    assert "oem-1" not in html
    assert "payment-1" not in html
