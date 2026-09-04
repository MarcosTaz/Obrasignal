from vertical_apps.industrial_claims.web import create_app


def test_vindorum_console_is_self_contained_and_exception_review_only(tmp_path):
    client = create_app(tmp_path / "console.sqlite3").test_client()
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    lower = html.lower()

    assert "VINDORUM" in html
    assert "Exception review control" in html
    assert "The normal customer journey is self-service" in html
    assert "Exception review workflow" in html
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
    assert "authorized secure evidence path" in lower
    assert "the creator cannot self-approve" in lower
    assert "selected dossier" in lower
    assert "raw document content is not returned" in lower
    assert "notice deadline values are declared for review" in lower
    assert "currency is explicit and immutable" in lower
    assert "declare for review: no notice deadline applies" in lower
    assert "workflow findings" in lower
    assert "approve for internal workflow" in lower
    assert "settlement/closure evidence is captured through the authorized secure evidence path" in lower
    assert "final cumulative outcome" in lower
    assert "ready_for_review" in lower
    assert "approved" in lower
    assert "recovery dossier preserves evidence state" in lower
    assert "actionable findings" not in lower
    for foreign in ("Certactum", "Supplier Recovery", "CausLedger"):
        assert foreign not in html
    assert 'maxlength="512"' in html
    assert 'maxlength="2048"' in html
    assert 'maxlength="4000"' in html
    assert "http://" not in html
    assert "https://" not in html
    assert "<style" not in lower
    assert "<script>" not in lower


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
    assert 'history.scrollRestoration = "manual"' in javascript
    assert "withBusy" in javascript
    assert "sessionStorage" in javascript


def test_console_shell_contains_no_tenant_or_case_data(tmp_path):
    client = create_app(tmp_path / "console.sqlite3").test_client()
    html = client.get("/").get_data(as_text=True)
    assert "alpha" not in html
    assert "oem-1" not in html
    assert "payment-1" not in html
