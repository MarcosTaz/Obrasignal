import json
import sqlite3
from types import SimpleNamespace

from flask import Flask

from opportunity_lifecycle import ensure_lifecycle_table
from readiness_api import install_readiness_api


def _db_factory(path):
    def open_db():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    return open_db


def _seed(path, *, actionable=1, lifecycle_status="OPEN"):
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE tenders (
            id INTEGER PRIMARY KEY,
            source TEXT,
            external_id TEXT,
            deadline TEXT,
            value REAL
        )"""
    )
    ensure_lifecycle_table(conn)
    conn.execute(
        "INSERT INTO tenders(id,source,external_id,deadline,value) VALUES(1,'TEST','opp-1','2030-01-10T12:00:00+00:00',100000)"
    )
    conn.execute(
        """INSERT INTO opportunity_lifecycle(
            source,external_id,is_actionable,lifecycle_status,lifecycle_reason,source_updated_at,last_observed
        ) VALUES('TEST','opp-1',?,?,NULL,'2030-01-01T00:00:00+00:00','2030-01-01T00:00:00+00:00')""",
        (actionable, lifecycle_status),
    )
    conn.commit()
    conn.close()


def test_endpoint_derives_account_from_authenticated_identity_and_ignores_query_account(tmp_path):
    db_path = str(tmp_path / "readiness.db")
    _seed(db_path)
    app = Flask(__name__)
    install_readiness_api(
        app,
        _db_factory(db_path),
        identity_provider=lambda: SimpleNamespace(account_id="tenant-a"),
        profile_loader=lambda account_id: {"account_id": account_id, "min_value": 50000, "max_value": 200000},
    )

    response = app.test_client().get("/api/v1/opportunities/1/readiness?account_id=tenant-b")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["account_id"] == "tenant-a"
    assert payload["overall_status"] == "UNKNOWN"  # requirements unavailable: no false READY
    assert any(item["code"] == "eligibility_requirements_unavailable" for item in payload["unknown_items"])


def test_endpoint_consumes_injected_public_requirements_contract(tmp_path):
    db_path = str(tmp_path / "requirements.db")
    _seed(db_path)
    app = Flask(__name__)
    seen = {}

    def resolver(account_id, opportunity, company_state):
        seen["account_id"] = account_id
        seen["external_id"] = opportunity["external_id"]
        seen["company_account"] = company_state["account_id"]
        return [{
            "name": "ISO 9001",
            "mandatory": True,
            "status": "MET",
            "source_ref": "TEST:opp-1",
            "evidence_ref": "TEST:opp-1#requirements[0]",
        }]

    install_readiness_api(
        app,
        _db_factory(db_path),
        identity_provider=lambda: SimpleNamespace(account_id="tenant-a"),
        profile_loader=lambda account_id: {"account_id": account_id, "min_value": 50000, "max_value": 200000},
        requirements_resolver=resolver,
    )

    response = app.test_client().get("/api/v1/opportunities/1/readiness")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["dimensions"]["ELIGIBILITY"]["status"] == "READY"
    assert "TEST:opp-1#requirements[0]" in payload["evidence_refs"]
    assert seen == {"account_id": "tenant-a", "external_id": "opp-1", "company_account": "tenant-a"}


def test_canonical_signal_snapshot_supplies_only_approved_requirements_context(tmp_path):
    db_path = str(tmp_path / "signal-context.db")
    _seed(db_path)
    app = Flask(__name__)
    seen = {}

    def signal_loader(_conn, source, external_id, signal_type):
        assert (source, external_id, signal_type) == ("TEST", "opp-1", "TENDER")
        return {
            "currency": "EUR",
            "source_updated_at": "2030-01-02T00:00:00+00:00",
            "normalized_json": json.dumps({
                "source": "EVIL",
                "external_id": "spoofed",
                "deadline": "1999-01-01T00:00:00+00:00",
                "lifecycle_status": "CLOSED",
                "required_certifications": ["ISO 9001"],
                "minimum_turnover": 50000,
                "currency": "EUR",
            }),
        }

    def resolver(_account_id, opportunity, _company_state):
        seen.update(opportunity)
        return [{"name": "ISO 9001", "mandatory": True, "status": "MET"}]

    install_readiness_api(
        app,
        _db_factory(db_path),
        identity_provider=lambda: SimpleNamespace(account_id="tenant-a"),
        profile_loader=lambda account_id: {"account_id": account_id},
        requirements_resolver=resolver,
        signal_loader=signal_loader,
    )

    response = app.test_client().get("/api/v1/opportunities/1/readiness")
    assert response.status_code == 200
    assert seen["required_certifications"] == ["ISO 9001"]
    assert seen["minimum_turnover"] == 50000
    assert seen["currency"] == "EUR"
    assert seen["source"] == "TEST"
    assert seen["external_id"] == "opp-1"
    assert seen["deadline"] == "2030-01-10T12:00:00+00:00"
    assert seen["lifecycle_status"] == "OPEN"


def test_signal_loader_failure_is_optional_and_degrades(tmp_path):
    db_path = str(tmp_path / "signal-failure.db")
    _seed(db_path)
    app = Flask(__name__)

    def broken_signal(*_args):
        raise RuntimeError("signal store unavailable")

    install_readiness_api(
        app,
        _db_factory(db_path),
        identity_provider=lambda: SimpleNamespace(account_id="tenant-a"),
        profile_loader=lambda account_id: {"account_id": account_id},
        signal_loader=broken_signal,
    )
    response = app.test_client().get("/api/v1/opportunities/1/readiness")
    assert response.status_code == 200
    assert response.get_json()["overall_status"] == "UNKNOWN"


def test_profile_loader_failure_degrades_without_losing_authenticated_tenant(tmp_path):
    db_path = str(tmp_path / "profile-failure.db")
    _seed(db_path)
    app = Flask(__name__)

    def broken_profile(_account_id):
        raise RuntimeError("profile store unavailable")

    install_readiness_api(
        app,
        _db_factory(db_path),
        identity_provider=lambda: SimpleNamespace(account_id="tenant-a"),
        profile_loader=broken_profile,
    )

    response = app.test_client().get("/api/v1/opportunities/1/readiness")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["account_id"] == "tenant-a"
    assert payload["overall_status"] == "UNKNOWN"
    assert any(item["code"] == "eligibility_requirements_unavailable" for item in payload["unknown_items"])


def test_requirements_resolver_failure_degrades_to_unknown(tmp_path):
    db_path = str(tmp_path / "requirements-failure.db")
    _seed(db_path)
    app = Flask(__name__)

    def broken_requirements(*_args):
        raise RuntimeError("requirements subsystem unavailable")

    install_readiness_api(
        app,
        _db_factory(db_path),
        identity_provider=lambda: SimpleNamespace(account_id="tenant-a"),
        profile_loader=lambda account_id: {"account_id": account_id},
        requirements_resolver=broken_requirements,
    )

    response = app.test_client().get("/api/v1/opportunities/1/readiness")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["overall_status"] == "UNKNOWN"
    assert any(item["code"] == "eligibility_requirements_unavailable" for item in payload["unknown_items"])


def test_endpoint_returns_not_ready_for_closed_opportunity(tmp_path):
    db_path = str(tmp_path / "closed.db")
    _seed(db_path, actionable=0, lifecycle_status="CLOSED")
    app = Flask(__name__)
    install_readiness_api(
        app,
        _db_factory(db_path),
        identity_provider=lambda: SimpleNamespace(account_id="tenant-a"),
        profile_loader=lambda account_id: {"account_id": account_id},
    )

    payload = app.test_client().get("/api/v1/opportunities/1/readiness").get_json()
    assert payload["overall_status"] == "NOT_READY"
    assert any(item["code"] == "opportunity_not_actionable" for item in payload["blocking_items"])


def test_endpoint_returns_404_for_unknown_opportunity(tmp_path):
    db_path = str(tmp_path / "missing.db")
    _seed(db_path)
    app = Flask(__name__)
    install_readiness_api(
        app,
        _db_factory(db_path),
        identity_provider=lambda: SimpleNamespace(account_id="tenant-a"),
        profile_loader=lambda account_id: {"account_id": account_id},
    )

    response = app.test_client().get("/api/v1/opportunities/999/readiness")
    assert response.status_code == 404
    assert response.get_json() == {"error": "not_found"}


def test_endpoint_requires_authenticated_identity(tmp_path):
    db_path = str(tmp_path / "auth.db")
    _seed(db_path)
    app = Flask(__name__)

    def no_identity():
        raise RuntimeError("authentication required")

    install_readiness_api(
        app,
        _db_factory(db_path),
        identity_provider=no_identity,
        profile_loader=lambda account_id: {"account_id": account_id},
    )

    response = app.test_client().get("/api/v1/opportunities/1/readiness")
    assert response.status_code == 401
    assert response.get_json() == {"error": "authentication_required"}


def test_endpoint_rejects_identity_without_account_id(tmp_path):
    db_path = str(tmp_path / "empty-auth.db")
    _seed(db_path)
    app = Flask(__name__)
    install_readiness_api(
        app,
        _db_factory(db_path),
        identity_provider=lambda: SimpleNamespace(account_id=""),
        profile_loader=lambda account_id: {"account_id": account_id},
    )

    response = app.test_client().get("/api/v1/opportunities/1/readiness")
    assert response.status_code == 401
    assert response.get_json() == {"error": "authentication_required"}


def test_install_is_idempotent(tmp_path):
    db_path = str(tmp_path / "idempotent.db")
    _seed(db_path)
    app = Flask(__name__)
    kwargs = {
        "identity_provider": lambda: SimpleNamespace(account_id="tenant-a"),
        "profile_loader": lambda account_id: {"account_id": account_id},
    }
    install_readiness_api(app, _db_factory(db_path), **kwargs)
    install_readiness_api(app, _db_factory(db_path), **kwargs)
    routes = [rule.rule for rule in app.url_map.iter_rules() if rule.rule.endswith("/readiness")]
    assert routes == ["/api/v1/opportunities/<int:opportunity_id>/readiness"]
