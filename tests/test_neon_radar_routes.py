"""Actual /api/v1/profile route under the staged Neon membership gate."""
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import UUID
import api
import neon_company_access
import psycopg

USER = "11111111-1111-4111-8111-111111111111"
A = "22222222-2222-4222-8222-222222222222"
B = "33333333-3333-4333-8333-333333333333"
ISSUER = "https://neon.test"

class Cursor:
    def __init__(self): self.params = None
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, query, params):
        assert 'neon_auth.member' in query
        self.params = params
    def fetchone(self):
        return (1,) if self.params == (UUID(USER), UUID(A)) else None

class Connection:
    def cursor(self): return Cursor()

def test_radar_profile_company_isolation(monkeypatch, tmp_path):
    monkeypatch.setenv("OBRASIGNAL_DB", str(tmp_path / "radar.db"))
    monkeypatch.setenv("OBRASIGNAL_NEON_COMPANY_AUTH", "staging")
    monkeypatch.setenv("OBRASIGNAL_NEON_STAGING_ISSUER", ISSUER)
    monkeypatch.setenv("OBRASIGNAL_NEON_STAGING_DATABASE_URL", "staging-secret-not-used")
    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: nullcontext(Connection()))
    monkeypatch.setattr(api, "configured_identity", lambda: SimpleNamespace(
        authenticated=True, subject=USER, account_id="untrusted-subject",
        claims={"iss": ISSUER}))
    client = api.APP.test_client()
    headers = {"X-ObraSignal-Company-ID": A}
    allowed = client.get("/api/v1/profile", headers=headers)
    assert allowed.status_code == 200
    assert allowed.json["account_id"] == A
    headers["X-ObraSignal-Company-ID"] = B
    denied = client.get("/api/v1/profile", headers=headers)
    assert denied.status_code == 401
    headers["X-ObraSignal-Company-ID"] = "not-a-uuid"
    assert client.get("/api/v1/profile", headers=headers).status_code == 401
