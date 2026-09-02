from vertical_apps.industrial_claims.web import create_app


def test_operator_console_is_self_contained_and_exposes_safe_assisted_journey(tmp_path):
    client = create_app(tmp_path / "console.sqlite3").test_client()
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Certactum" in html
    assert "CausLedger" not in html
    assert "Industrial Claims operator console" in html
    assert 'id="analyze-form"' in html
    assert 'id="claim_currency"' in html
    assert 'id="refresh-queue"' in html
    assert 'id="queue-list"' in html
    assert 'id="detail-result"' in html
    assert 'id="review-form"' in html
    assert 'id="action-form"' in html
    assert 'id="resolve-form"' not in html
    assert 'name="commercial_basis_content"' not in html
    assert 'name="event_evidence_content"' not in html
    assert 'name="cost_evidence_content"' not in html
    assert "Reference-only intake" in html
    assert "Create reference-only candidate" in html
    assert "authorized secure evidence path" in html
    assert "Do not paste bank statements" in html
    assert "Four-eyes review" in html
    assert "selected dossier" in html.lower()
    assert "inspect the selected dossier before review" in html.lower()
    assert "raw document content is not returned" in html.lower()
    assert "unknown notice deadline" in html.lower()
    assert "neither state is a legal conclusion" in html.lower()
    assert "established recoverability" in html.lower()
    assert "currency is explicit and immutable" in html.lower()
    assert "declare for review: no notice deadline applies" in html.lower()
    assert "analyst declarations for independent review" in html.lower()
    assert "verified: no notice deadline applies" not in html.lower()
    assert "workflow findings" in html.lower()
    assert "approve for internal workflow" in html.lower()
    assert "approved for internal workflow only" in html.lower()
    assert "does not establish a legal entitlement" in html.lower()
    assert "authorize customer contact" in html.lower()
    assert "authorize external claim submission" in html.lower()
    assert "not an installment" in html.lower()
    assert "expired declared date" in html.lower()
    assert "not proof of non-recoverability" in html.lower()
    assert "actionable findings" not in html.lower()
    assert 'maxlength="512"' in html
    assert 'maxlength="2048"' in html
    assert 'maxlength="4000"' in html
    assert "http://" not in html
    assert "https://" not in html
    assert "<style" not in html.lower()
    assert "<script>" not in html.lower()


def test_synthetic_console_exposes_document_and_outcome_forms_only_after_explicit_opt_in(tmp_path):
    client = create_app(
        tmp_path / "console-synthetic.sqlite3",
        allow_inline_evidence_content=True,
    ).test_client()
    html = client.get("/").get_data(as_text=True)
    assert "Synthetic/local mode is active" in html
    assert 'name="commercial_basis_content"' in html
    assert 'name="event_evidence_content"' in html
    assert 'name="cost_evidence_content"' in html
    assert 'id="resolve-form"' in html
    assert 'id="evidence_content"' in html
    assert 'id="final_cumulative"' in html
    assert "synthetic final cumulative documented outcome" in html.lower()


def test_console_has_strict_browser_headers_and_safe_dossier_renderer(tmp_path):
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
    assert "async function loadDetail(id)" in javascript
    assert 'send(`/findings/${encodeURIComponent(findingId)}`' in javascript
    assert "await loadDetail(id)" in javascript
    assert "await loadDetail(result.body.finding_id)" in javascript
    assert 'const resolveForm = node("resolve-form")' in javascript
    assert "if (resolveForm) resolveForm.addEventListener" in javascript
    assert "No workflow findings for this verified role and tenant." in javascript
    assert "No actionable findings" not in javascript


def test_console_shell_contains_no_tenant_or_case_data(tmp_path):
    client = create_app(tmp_path / "console.sqlite3").test_client()
    html = client.get("/").get_data(as_text=True)
    assert "alpha" not in html
    assert "oem-1" not in html
    assert "payment-1" not in html
