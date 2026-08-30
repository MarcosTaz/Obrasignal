from vertical_apps.industrial_claims.web import create_app


def test_console_exposes_safe_amendment_mode_without_raw_document_reload(tmp_path):
    client = create_app(tmp_path / "console-amendment.sqlite3").test_client()
    javascript = client.get("/static/console.js").get_data(as_text=True)

    assert "innerHTML" not in javascript
    assert 'input.id = "amend_finding_id"' in javascript
    assert 'input.maxLength = 2048' in javascript
    assert 'const amendFindingId = String(payload.amend_finding_id || "").trim()' in javascript
    assert "delete payload.amend_finding_id" in javascript
    assert '`/findings/${encodeURIComponent(amendFindingId)}/amend`' in javascript
    assert ' : "/analyze"' in javascript
    assert "creates a new revision and requires fresh independent review" in javascript
    assert "raw documents are not reloaded from storage" in javascript
    assert "await loadDetail(result.body.finding_id)" in javascript
