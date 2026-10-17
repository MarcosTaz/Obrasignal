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
