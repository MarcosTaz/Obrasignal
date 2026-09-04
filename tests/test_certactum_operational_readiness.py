import sqlite3

from vertical_apps.industrial_claims.operational_readiness import build_operational_readiness


def _database(path):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE health (id INTEGER PRIMARY KEY)")
        connection.commit()


def test_readiness_is_secret_free_and_reports_external_dependencies_as_warnings(tmp_path, monkeypatch):
    database = tmp_path / "certactum.sqlite3"
    _database(database)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.delenv("CERTACTUM_WORM_PROVIDER", raising=False)
    monkeypatch.delenv("CERTACTUM_TIMESTAMP_PROVIDER", raising=False)

    report = build_operational_readiness(database)
    assert report["product"] == "Certactum"
    assert report["status"] == "ready_with_warnings"
    assert "authentication" in report["warnings"]
    assert "external_proof" in report["warnings"]
    assert report["blocking_failures"] == []
    text = repr(report).lower()
    assert "password" not in text
    assert "token" not in text
    assert report["truth_boundary"]["production_certification_claimed"] is False
    assert report["truth_boundary"]["court_acceptance_guaranteed"] is False


def test_missing_database_is_blocking_and_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    report = build_operational_readiness(tmp_path / "missing.sqlite3")
    assert report["status"] == "not_ready"
    assert "database" in report["blocking_failures"]


def test_declared_external_providers_do_not_invent_certification(tmp_path, monkeypatch):
    database = tmp_path / "certactum.sqlite3"
    _database(database)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("CERTACTUM_WORM_PROVIDER", "configured-provider")
    monkeypatch.setenv("CERTACTUM_TIMESTAMP_PROVIDER", "configured-provider")

    report = build_operational_readiness(database)
    proof = next(item for item in report["checks"] if item["name"] == "external_proof")
    assert proof["status"] == "warn"
    assert proof["detail"] == "external_providers_declared_unverified"
    assert report["truth_boundary"]["external_provider_names_are_not_verification"] is True
    assert report["truth_boundary"]["real_confidential_intake_requires_live_production_trust_gate"] is True
    assert report["truth_boundary"]["production_certification_claimed"] is False
