from flask import Flask

from cloud_switching.integration import register_cloud_switching


def test_registration_is_idempotent_and_uses_canonical_api_boundary(tmp_path):
    app = Flask(__name__)
    register_cloud_switching(
        app,
        database_path=str(tmp_path / "cloud.db"),
        resolve_tenant=lambda: "tenant-a",
    )
    register_cloud_switching(
        app,
        database_path=str(tmp_path / "cloud.db"),
        resolve_tenant=lambda: "tenant-a",
    )
    assert "cloud_switching" in app.blueprints
    client = app.test_client()
    response = client.get("/api/v1/cloud-switching/health")
    assert response.status_code == 200
    assert response.get_json()["service"] == "cloud-switching"


def test_production_prefix_does_not_expose_standalone_route(tmp_path):
    app = Flask(__name__)
    register_cloud_switching(
        app,
        database_path=str(tmp_path / "cloud.db"),
        resolve_tenant=lambda: "tenant-a",
    )
    client = app.test_client()
    assert client.get("/cloud-switching/health").status_code == 404
    assert client.get("/api/v1/cloud-switching/health").status_code == 200
