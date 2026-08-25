import app
import api
import pursuit_workspace_api


def _seed(monkeypatch, tmp_path):
    db_path = tmp_path / "workspace.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    monkeypatch.setattr(app, "DB", str(db_path))
    app.init_db()
    conn = app.db()
    conn.execute("""INSERT INTO tenders(source,external_id,title,buyer,country,value,deadline,publication_date,url,score,first_seen,last_seen)
                    VALUES ('TED','W-1','Bridge works','City','PRT','1 EUR','2099-01-01','2026-08-25','https://example.test/w',80,'2026-08-25','2026-08-25')""")
    conn.commit()
    oid = conn.execute("SELECT id FROM tenders WHERE external_id='W-1'").fetchone()[0]
    conn.close()
    return oid


def test_workspace_api_create_get_patch(monkeypatch, tmp_path):
    oid = _seed(monkeypatch, tmp_path)
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "company-a")
    client = api.APP.test_client()
    created = client.post(f"/api/v1/opportunities/{oid}/workspace")
    again = client.post(f"/api/v1/opportunities/{oid}/workspace")
    blocker = client.post(f"/api/v1/opportunities/{oid}/workspace/blockers", json={"title": "Waiting for quote"})
    note = client.post(f"/api/v1/opportunities/{oid}/workspace/notes", json={"body": "Internal note"})
    changed = client.patch(f"/api/v1/opportunities/{oid}/workspace", json={"review_state": "IN_REVIEW", "submission_state": "PREPARING"})
    view = client.get(f"/api/v1/opportunities/{oid}/workspace")
    assert created.status_code == 201
    assert created.get_json()["workspace"]["workspace_id"] == again.get_json()["workspace"]["workspace_id"]
    assert blocker.status_code == 201 and note.status_code == 201
    assert changed.get_json()["workspace"]["review_state"] == "IN_REVIEW"
    body = view.get_json()
    assert body["opportunity"]["external_id"] == "W-1"
    assert body["notes"][0]["body"] == "Internal note"
    assert body["sections"]["economics"]["status"] == "UNAVAILABLE"


def test_workspace_api_cross_tenant_isolation(monkeypatch, tmp_path):
    oid = _seed(monkeypatch, tmp_path)
    client = api.APP.test_client()
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "company-a")
    assert client.post(f"/api/v1/opportunities/{oid}/workspace").status_code == 201
    assert client.post(f"/api/v1/opportunities/{oid}/workspace/notes", json={"body": "A private note"}).status_code == 201
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "company-b")
    assert client.get(f"/api/v1/opportunities/{oid}/workspace").status_code == 404
    assert client.post(f"/api/v1/opportunities/{oid}/workspace/notes", json={"body": "B write"}).status_code == 404


def test_workspace_api_rejects_arbitrary_owner_and_invalid_progress(monkeypatch, tmp_path):
    oid = _seed(monkeypatch, tmp_path)
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "company-a")
    client = api.APP.test_client()
    client.post(f"/api/v1/opportunities/{oid}/workspace")
    owner = client.patch(f"/api/v1/opportunities/{oid}/workspace", json={"owner_id": "other-user"})
    progress = client.patch(f"/api/v1/opportunities/{oid}/workspace", json={"submission_state": "73_PERCENT"})
    oversized = client.post(f"/api/v1/opportunities/{oid}/workspace/notes", json={"body": "x" * 8001})
    assert owner.status_code == 403
    assert progress.status_code == 400
    assert oversized.status_code == 400
