import sqlite3

from vertical_apps.industrial_claims.operational_readiness import build_operational_readiness


def _database(path):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE health (id INTEGER PRIMARY KEY)")
        connection.commit()


def test_readiness_is_secret_free_and_external_dependencies_block_real_intake(tmp_path, monkeypatch):
    database = tmp_path / "certactum.sqlite3"
    _database(database)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.delenv("CERTACTUM_WORM_PROVIDER", raising=False)
    monkeypatch.delenv("CERTACTUM_TIMESTAMP_PROVIDER", raising=False)

    report = build_operational_readiness(database)
    assert report["product"] == "Certactum"
    assert report["status"] == "not_ready"
    assert "authentication" in report["warnings"]
    assert "worm_storage" in report["blocking_failures"]
    assert "trusted_timestamp" in report["blocking_failures"]
    assert report["activation"]["automatic"] is True
    assert report["activation"]["real_evidence_intake_enabled"] is False
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
    assert report["activation"]["real_evidence_intake_enabled"] is False


def test_declared_external_providers_do_not_invent_certification_or_bypass_auth(tmp_path, monkeypatch):
    database = tmp_path / "certactum.sqlite3"
    _database(database)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("CERTACTUM_WORM_PROVIDER", "configured-provider")
    monkeypatch.setenv("CERTACTUM_TIMESTAMP_PROVIDER", "configured-provider")

    report = build_operational_readiness(database)
    worm = next(item for item in report["checks"] if item["name"] == "worm_storage")
    timestamp = next(item for item in report["checks"] if item["name"] == "trusted_timestamp")
    assert worm["status"] == "pass"
    assert timestamp["status"] == "pass"
    assert report["activation"]["real_evidence_intake_enabled"] is False
    assert report["truth_boundary"]["production_certification_claimed"] is False
    assert report["truth_boundary"]["provider_declaration_is_not_external_certification"] is True
