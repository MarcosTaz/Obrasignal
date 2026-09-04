import sqlite3
from types import SimpleNamespace

import vertical_apps.industrial_claims.operational_readiness as readiness
from vertical_apps.industrial_claims.operational_readiness import build_operational_readiness


def _database(path):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE health (id INTEGER PRIMARY KEY)")
        connection.commit()


class _Gate:
    def __init__(self, *, blockers=(), providers=None):
        self.blockers = tuple(blockers)
        self.providers = providers or {"worm": "worm-provider", "timestamp": "timestamp-provider"}

    def evaluate(self, *, verified_claims):
        assert verified_claims == {"aal": "aal2"}
        return SimpleNamespace(blockers=self.blockers, providers=self.providers)


def test_readiness_is_secret_free_and_external_dependencies_block_real_intake(tmp_path, monkeypatch):
    database = tmp_path / "vindorum.sqlite3"
    _database(database)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setattr(readiness, "configured_production_trust_gate", lambda: None)
    report = build_operational_readiness(database)
    assert report["product"] == "VINDORUM"
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
    monkeypatch.setattr(readiness, "configured_production_trust_gate", lambda: None)
    report = build_operational_readiness(tmp_path / "missing.sqlite3")
    assert report["status"] == "not_ready"
    assert "database" in report["blocking_failures"]
    assert report["activation"]["real_evidence_intake_enabled"] is False


def test_declared_external_providers_cannot_enable_intake_without_live_gate(tmp_path, monkeypatch):
    database = tmp_path / "vindorum.sqlite3"
    _database(database)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("VINDORUM_WORM_PROVIDER", "declared-only")
    monkeypatch.setenv("VINDORUM_TIMESTAMP_PROVIDER", "declared-only")
    monkeypatch.setattr(readiness, "configured_production_trust_gate", lambda: None)
    report = build_operational_readiness(database)
    worm = next(item for item in report["checks"] if item["name"] == "worm_storage")
    timestamp = next(item for item in report["checks"] if item["name"] == "trusted_timestamp")
    assert worm == {
        "name": "worm_storage",
        "status": "fail",
        "detail": "live_worm_probe_unconfigured",
        "blocking": True,
    }
    assert timestamp == {
        "name": "trusted_timestamp",
        "status": "fail",
        "detail": "live_timestamp_probe_unconfigured",
        "blocking": True,
    }
    assert report["activation"]["real_evidence_intake_enabled"] is False
    assert report["truth_boundary"]["provider_declaration_cannot_enable_intake"] is True


def test_live_external_probes_and_production_auth_are_required_to_enable_intake(tmp_path, monkeypatch):
    database = tmp_path / "vindorum.sqlite3"
    _database(database)
    monkeypatch.setattr(
        readiness,
        "authentication_health",
        lambda: {"mode": "provider", "provider_status": "ready", "config_present": True},
    )
    monkeypatch.setattr(readiness, "configured_production_trust_gate", lambda: _Gate())

    report = build_operational_readiness(database)

    assert report["status"] == "ready"
    assert report["blocking_failures"] == []
    assert report["warnings"] == []
    assert report["activation"]["real_evidence_intake_enabled"] is True
    assert report["activation"]["rule"] == (
        "database_ok AND production_auth_ok AND live_worm_probe_ok AND live_timestamp_probe_ok"
    )
    assert report["truth_boundary"]["external_controls_require_live_probe_receipts"] is True
    assert report["truth_boundary"]["per_request_mfa_aal2_still_required"] is True


def test_failed_live_control_probe_keeps_intake_closed(tmp_path, monkeypatch):
    database = tmp_path / "vindorum.sqlite3"
    _database(database)
    monkeypatch.setattr(
        readiness,
        "authentication_health",
        lambda: {"mode": "provider", "provider_status": "ready", "config_present": True},
    )
    monkeypatch.setattr(
        readiness,
        "configured_production_trust_gate",
        lambda: _Gate(blockers=("timestamp_unverified",)),
    )

    report = build_operational_readiness(database)
    timestamp = next(item for item in report["checks"] if item["name"] == "trusted_timestamp")

    assert timestamp["status"] == "fail"
    assert "trusted_timestamp" in report["blocking_failures"]
    assert report["activation"]["real_evidence_intake_enabled"] is False
