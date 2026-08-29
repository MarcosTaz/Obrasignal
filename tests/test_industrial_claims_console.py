from vertical_apps.industrial_claims.web import create_app


def test_operator_console_is_self_contained_and_exposes_full_assisted_journey(tmp_path):
    client = create_app(tmp_path / "console.sqlite3").test_client()
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "CausLedger" in html
    assert "Industrial Claims operator console" in html
    assert 'id="analyze-form"' in html
    assert 'id="claim_currency"' in html
    assert 'id="refresh-queue"' in html
    assert 'id="queue-list"' in html
    assert 'id="review-form"' in html
    assert 'id="action-form"' in html
    assert 'id="resolve-form"' in html
    assert "Four-eyes review" in html
    assert "unknown notice deadline" in html.lower()
    assert "not a legal conclusion" in html.lower()
    assert "established recoverability" in html.lower()
    assert "currency is explicit and immutable" in html.lower()
    assert 'id="currency" value=' not in html
    assert "http://" not in html
    assert "https://" not in html
    assert "<style" not in html.lower()
    assert "<script>" not in html.lower()


def test_console_has_strict_browser_headers_and_no_html_injection_renderer(tmp_path):
    client = create_app(tmp_path / "console.sqlite3").test_client()
    response = client.get("/")

    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "style-src 'self'" in csp
    assert "'unsafe-inline'" not in csp
    assert "frame-ancestors 'none'" in csp
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"

    javascript = client.get("/static/console.js").get_data(as_text=True)
    assert "innerHTML" not in javascript
    assert "textContent" in javascript
    assert "replaceChildren" in javascript
    assert 'send("/findings"' in javascript
    assert "createElement(\"button\")" in javascript
    assert "finding.currency_unit" in javascript


def test_console_shell_contains_no_tenant_or_case_data(tmp_path):
    client = create_app(tmp_path / "console.sqlite3").test_client()
    html = client.get("/").get_data(as_text=True)

    assert "alpha" not in html
    assert "oem-1" not in html
    assert "payment-1" not in html
