from cloud_switching.standalone import create_app


def test_standalone_pilot_exposes_canonical_v1_health(tmp_path):
    app = create_app(
        database_path=tmp_path / "pilot.db",
        resolve_tenant=lambda: "tenant-a",
    )
    client = app.test_client()
    response = client.get("/api/v1/cloud-switching/health")
    assert response.status_code == 200
    assert response.get_json() == {"service": "cloud-switching", "status": "ok"}


def test_standalone_pilot_initializes_persistent_workspace(tmp_path):
    path = tmp_path / "pilot.db"
    create_app(database_path=path, resolve_tenant=lambda: "tenant-a")
    assert path.exists()
