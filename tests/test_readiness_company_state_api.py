import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from flask import Flask

from company_state import CompanyFact, CompanyState, FactCategory, KnowledgeState, Provenance, ProvenanceBasis
from opportunity_lifecycle import ensure_lifecycle_table
from readiness_api import install_readiness_api

NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)


def _db_factory(path):
    def open_db():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    return open_db


def _seed(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE tenders (id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, deadline TEXT, value REAL)")
    ensure_lifecycle_table(conn)
    conn.execute("INSERT INTO tenders(id,source,external_id,deadline,value) VALUES(1,'TEST','opp-1','2030-01-10T12:00:00+00:00',100000)")
    conn.execute("INSERT INTO opportunity_lifecycle(source,external_id,is_actionable,lifecycle_status,lifecycle_reason,source_updated_at,last_observed) VALUES('TEST','opp-1',1,'OPEN',NULL,'2030-01-01T00:00:00+00:00','2030-01-01T00:00:00+00:00')")
    conn.commit()
    conn.close()


def _state(account):
    fact = CompanyFact(
        FactCategory.QUALIFICATION,
        "qualification.iso-9001",
        KnowledgeState.FACT,
        {"name": "ISO 9001", "status": "HELD", "validity": "VALID"},
        Provenance(ProvenanceBasis.VERIFIED, source_ref="registry", evidence_ref="company-evidence", observed_at=NOW, verified_at=NOW),
        effective_until=NOW + timedelta(days=3650),
    )
    return CompanyState(account, NOW, (fact,))


def test_api_uses_authenticated_tenant_and_company_state_object(tmp_path):
    path = str(tmp_path / "readiness.db")
    _seed(path)
    app = Flask(__name__)
    seen = {}
    def resolver(account_id, opportunity, state):
        seen.update(account=account_id, state_type=type(state).__name__, state_account=state.account_id)
        return [{"name": "fixture", "mandatory": True, "status": "UNKNOWN"}]
    install_readiness_api(
        app, _db_factory(path),
        identity_provider=lambda: SimpleNamespace(account_id="tenant-a"),
        company_state_loader=lambda account: _state(account),
        profile_loader=lambda account: {"account_id": account},
        requirements_resolver=resolver,
        signal_loader=lambda *_: None,
        clock=NOW,
    )
    response = app.test_client().get("/api/v1/opportunities/1/readiness?account_id=tenant-b")
    assert response.status_code == 200
    assert response.get_json()["account_id"] == "tenant-a"
    assert seen == {"account": "tenant-a", "state_type": "CompanyState", "state_account": "tenant-a"}


def test_api_fails_closed_on_mismatched_company_state(tmp_path):
    path = str(tmp_path / "tenant-boundary.db")
    _seed(path)
    app = Flask(__name__)
    install_readiness_api(
        app, _db_factory(path),
        identity_provider=lambda: SimpleNamespace(account_id="tenant-a"),
        company_state_loader=lambda _account: _state("tenant-b"),
        profile_loader=lambda account: {"account_id": account},
        signal_loader=lambda *_: None,
        clock=NOW,
    )
    response = app.test_client().get("/api/v1/opportunities/1/readiness")
    assert response.status_code == 503
    assert response.get_json() == {"error": "readiness_unavailable"}
    assert "tenant-b" not in response.get_data(as_text=True)


def test_company_state_storage_failure_becomes_critical_unknown(tmp_path):
    path = str(tmp_path / "storage.db")
    _seed(path)
    app = Flask(__name__)
    def broken(_account):
        raise sqlite3.OperationalError("storage unavailable")
    install_readiness_api(
        app, _db_factory(path),
        identity_provider=lambda: SimpleNamespace(account_id="tenant-a"),
        company_state_loader=broken,
        profile_loader=lambda account: {"account_id": account},
        requirements_resolver=lambda *_: [{"name": "fixture", "mandatory": True, "status": "MET"}],
        signal_loader=lambda *_: None,
        clock=NOW,
    )
    payload = app.test_client().get("/api/v1/opportunities/1/readiness").get_json()
    assert payload["overall_status"] == "UNKNOWN"
    assert any(item["code"] == "company_state_unavailable" for item in payload["unknown_items"])


def test_requirements_provider_failure_becomes_unknown(tmp_path):
    path = str(tmp_path / "requirements.db")
    _seed(path)
    app = Flask(__name__)
    def broken(*_args):
        raise RuntimeError("requirements unavailable")
    install_readiness_api(
        app, _db_factory(path),
        identity_provider=lambda: SimpleNamespace(account_id="tenant-a"),
        company_state_loader=lambda account: _state(account),
        profile_loader=lambda account: {"account_id": account},
        requirements_resolver=broken,
        signal_loader=lambda *_: None,
        clock=NOW,
    )
    payload = app.test_client().get("/api/v1/opportunities/1/readiness").get_json()
    assert payload["overall_status"] == "UNKNOWN"
    assert any(item["code"] == "eligibility_requirements_unavailable" for item in payload["unknown_items"])
