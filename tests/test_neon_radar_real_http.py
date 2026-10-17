"""HTTP regression of the REAL Radar blueprint's staged tenant boundary.

Synthetic identities and in-memory fakes only: no live Neon or production writes.
The JWT signature verifier is separately exercised by test_neon_jwt_compat.py.
"""
from types import SimpleNamespace

import api
import psycopg
import pytest

ISSUER = "https://neon-auth-test.invalid"
USER = "11111111-1111-4111-8111-111111111111"
OTHER_USER = "44444444-4444-4444-8444-444444444444"
ORG_A = "22222222-2222-4222-8222-222222222222"
ORG_B = "33333333-3333-4333-8333-333333333333"


class FakeCursor:
    def __init__(self, allowed):
        self.allowed = allowed
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        assert "neon_auth.member" in sql
        assert "%s" in sql
        self.params = params

    def fetchone(self):
        user, org = map(str, self.params)
        return (1,) if (user, org) in self.allowed else None


class FakeNeonConnection:
    def __init__(self, allowed):
        self.allowed = allowed

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return FakeCursor(self.allowed)


class FakeRadarConnection:
    def close(self):
        pass


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_NEON_COMPANY_AUTH", "staging")
    monkeypatch.setenv("OBRASIGNAL_NEON_STAGING_ISSUER", ISSUER)
    monkeypatch.setenv("OBRASIGNAL_NEON_STAGING_DATABASE_URL", "synthetic-only")
    current = {"user": USER, "issuer": ISSUER, "authenticated": True}
    memberships = {(USER, ORG_A)}
    monkeypatch.setattr(
        api, "configured_identity",
        lambda: SimpleNamespace(
            authenticated=current["authenticated"],
            subject=current["user"],
            claims={"iss": current["issuer"]},
            account_id="forged-tenant-claim",
        ),
    )
    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: FakeNeonConnection(memberships))
    monkeypatch.setattr(api, "_db", lambda: FakeRadarConnection())
    seen = []
    monkeypatch.setattr(api, "ensure_account", lambda _conn, account_id: seen.append(account_id))
    return api.APP.test_client(), current, memberships, seen


def test_real_radar_sources_requires_company_membership(client):
    http, current, memberships, seen = client
    path = "/api/v1/sources"
    def request(company=None):
        headers = {"X-ObraSignal-Company-ID": company} if company else {}
        return http.get(path, headers=headers)

    assert request().status_code == 401
    assert request(ORG_B).status_code == 401
    assert seen == []
    allowed = request(ORG_A)
    assert allowed.status_code == 200
    assert allowed.json["account_id"] == ORG_A
    assert seen == [ORG_A]
    memberships.add((USER, ORG_B))
    switched = request(ORG_B)
    assert switched.status_code == 200
    assert switched.json["account_id"] == ORG_B
    assert seen == [ORG_A, ORG_B]
    current["user"] = OTHER_USER
    assert request(ORG_A).status_code == 401
    current["user"] = USER
    current["issuer"] = "https://attacker.invalid"
    assert request(ORG_A).status_code == 401
    current["issuer"] = ISSUER
    current["authenticated"] = False
    assert request(ORG_A).status_code == 401


def test_bad_company_identifiers_fail_closed(client):
    http, _current, _memberships, seen = client
    for candidate in ("not-a-uuid", "../other", " ", "00000000-0000-0000-0000-000000000000x"):
        result = http.get("/api/v1/sources", headers={"X-ObraSignal-Company-ID": candidate})
        assert result.status_code == 401
    assert seen == []


def test_real_radar_profile_write_isolated_by_membership(client, monkeypatch):
    http, current, memberships, seen = client
    writes = []
    profile = {"name": "Synthetic Company A", "activity": "building"}
    monkeypatch.setattr(api, "load_profile", lambda account_id: dict(profile, account_id=account_id))
    monkeypatch.setattr(api, "derive_profile", lambda activity, merged: dict(merged))
    monkeypatch.setattr(api, "save_profile", lambda normalized, account_id: (
        writes.append(account_id) or dict(normalized)
    ))
    monkeypatch.setattr(api, "bootstrap_account", lambda account_id: {"account_id": account_id})
    url = "/api/v1/profile"
    headers = lambda org: {"X-ObraSignal-Company-ID": org}
    rejected = http.post(url, headers=headers(ORG_B), json={"name": "not allowed"})
    assert rejected.status_code == 401
    assert writes == []
    allowed = http.post(url, headers=headers(ORG_A), json={"name": "synthetic update"})
    assert allowed.status_code == 200
    assert allowed.json["account_id"] == ORG_A
    assert writes == [ORG_A]
    current["user"] = OTHER_USER
    rejected_again = http.post(url, headers=headers(ORG_A), json={"name": "not allowed"})
    assert rejected_again.status_code == 401
    assert writes == [ORG_A]


def test_workflow_write_does_not_cross_company_boundary(client, monkeypatch):
    http, current, memberships, seen = client
    writes = []

    class TenderConnection:
        def execute(self, query, params):
            assert "FROM tenders" in query
            assert params == (42,)
            return self

        def fetchone(self):
            return {"source": "synthetic", "external_id": "T-42"}

        def close(self):
            pass

    monkeypatch.setattr(api, "_db", lambda: TenderConnection())
    monkeypatch.setattr(api, "set_workflow", lambda connection, account, source, external, status, note: (
        writes.append((account, source, external, status)) or {"status": status}
    ))
    url = "/api/v1/opportunities/42/workflow"
    headers = lambda org: {"X-ObraSignal-Company-ID": org}
    assert http.post(url, headers=headers(ORG_B), json={"status": "REVIEW"}).status_code == 401
    assert writes == []
    ok = http.post(url, headers=headers(ORG_A), json={"status": "REVIEW"})
    assert ok.status_code == 200
    assert ok.json["account_id"] == ORG_A
    assert writes == [(ORG_A, "synthetic", "T-42", "REVIEW")]
    current["user"] = OTHER_USER
    assert http.post(url, headers=headers(ORG_A), json={"status": "REJECT"}).status_code == 401
    assert len(writes) == 1


def test_alert_delivery_updates_only_authorized_company(client, monkeypatch):
    http, current, memberships, seen = client
    updates = []

    class UpdateResult:
        rowcount = 1

    class EventConnection:
        def execute(self, sql, params):
            assert "UPDATE opportunity_events" in sql
            assert "account_id=?" in sql
            updates.append(params)
            return UpdateResult()

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(api, "_db", lambda: EventConnection())
    url = "/api/v1/alerts/77/delivered"
    headers = lambda org: {"X-ObraSignal-Company-ID": org}
    assert http.post(url, headers=headers(ORG_B)).status_code == 401
    assert updates == []
    ok = http.post(url, headers=headers(ORG_A))
    assert ok.status_code == 200
    assert len(updates) == 1
    assert updates[0][1:] == (77, ORG_A)
    current["issuer"] = "https://impostor.invalid"
    assert http.post(url, headers=headers(ORG_A)).status_code == 401
    assert len(updates) == 1


def test_read_endpoints_fail_closed_before_db_access(client):
    http, current, memberships, seen = client
    protected_paths = (
        "/api/v1/stats",
        "/api/v1/workflow/stats",
        "/api/v1/opportunities",
        "/api/v1/opportunities/42",
        "/api/v1/opportunities/42/workflow",
        "/api/v1/alerts",
    )
    headers = {"X-ObraSignal-Company-ID": ORG_B}
    for path in protected_paths:
        response = http.get(path, headers=headers)
        assert response.status_code == 401, (path, response.status_code)
    assert seen == []


def test_membership_database_outage_returns_503_without_account_fallback(client, monkeypatch):
    http, current, memberships, seen = client

    def offline(*args, **kwargs):
        raise psycopg.OperationalError("synthetic connection failure")

    monkeypatch.setattr(psycopg, "connect", offline)
    response = http.get("/api/v1/sources", headers={"X-ObraSignal-Company-ID": ORG_A})
    assert response.status_code == 503
    assert response.json == {"error": "company_authorization_unavailable"}
    assert seen == []
