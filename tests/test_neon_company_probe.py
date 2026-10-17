"""HTTP authorization contract, isolated from production routing."""
from contextlib import nullcontext
from types import SimpleNamespace

from flask import Flask
from jwt import InvalidTokenError

from neon_company_probe import build_neon_company_probe

USER = "11111111-1111-4111-8111-111111111111"
ORG_A = "22222222-2222-4222-8222-222222222222"
ORG_B = "33333333-3333-4333-8333-333333333333"

class Verifier:
    def verify(self, token):
        if token != "valid":
            raise InvalidTokenError("bad token")
        return SimpleNamespace(subject=USER, claims={"iss": "neon-test"})

class Cursor:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, sql, params):
        self.params = params
    def fetchone(self):
        return (1,) if str(self.params[1]) == ORG_A else None

class Connection:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def cursor(self):
        return Cursor()

def test_http_company_probe_fail_closed():
    app = Flask(__name__)
    app.register_blueprint(build_neon_company_probe(Verifier(), lambda: Connection()))
    client = app.test_client()
    url = lambda org: "/__staging/neon/companies/" + org + "/access"
    assert client.get(url(ORG_A)).status_code == 401
    assert client.get(url(ORG_A), headers={"Authorization":"Bearer invalid"}).status_code == 401
    headers = {"Authorization":"Bearer valid"}
    yes = client.get(url(ORG_A), headers=headers)
    assert yes.status_code == 200
    assert yes.json["company_id"] == ORG_A
    assert client.get(url(ORG_B), headers=headers).status_code == 403


def test_probe_sanitizes_neon_database_outage():
    import psycopg
    app = Flask(__name__)
    def offline():
        raise psycopg.OperationalError("synthetic database secret must not leak")
    app.register_blueprint(build_neon_company_probe(Verifier(), offline))
    result = app.test_client().get(
        "/__staging/neon/companies/" + ORG_A + "/access",
        headers={"Authorization": "Bearer valid"},
    )
    assert result.status_code == 503
    assert result.json == {"error": "authorization_service_unavailable"}


def test_probe_sanitizes_jwks_outage():
    from auth_context_jwt import JwksUnavailableError

    class OfflineVerifier:
        def verify(self, token):
            raise JwksUnavailableError("synthetic provider secret must not leak")

    app = Flask(__name__)
    app.register_blueprint(build_neon_company_probe(OfflineVerifier(), lambda: Connection()))
    result = app.test_client().get(
        "/__staging/neon/companies/" + ORG_A + "/access",
        headers={"Authorization": "Bearer valid"},
    )
    assert result.status_code == 503
    assert result.json == {"error": "authorization_service_unavailable"}


def test_probe_rejects_missing_signed_identity_claims_before_database_access():
    from types import SimpleNamespace
    class IncompleteVerifier:
        def __init__(self, claims, subject):
            self.claims, self.subject = claims, subject
        def verify(self, token):
            return SimpleNamespace(claims=self.claims, subject=self.subject)

    for claims, subject in ((None, USER), ({}, USER), ({"iss": "neon-test"}, None)):
        app = Flask(__name__)
        called = []
        app.register_blueprint(build_neon_company_probe(
            IncompleteVerifier(claims, subject),
            lambda: (called.append(True), Connection())[1],
        ))
        result = app.test_client().get(
            "/__staging/neon/companies/" + ORG_A + "/access",
            headers={"Authorization": "Bearer valid"},
        )
        assert result.status_code == 401
        assert called == []


def test_probe_rejects_invalid_company_ids_without_database_access():
    app = Flask(__name__)
    calls = []
    app.register_blueprint(build_neon_company_probe(
        Verifier(), lambda: (calls.append(True), Connection())[1]
    ))
    client = app.test_client()
    for identifier in ("not-a-uuid", "00000000-0000-0000-0000-000000000000x", "other-company"):
        response = client.get(
            "/__staging/neon/companies/" + identifier + "/access",
            headers={"Authorization": "Bearer valid"},
        )
        assert response.status_code == 403
    assert calls == []
