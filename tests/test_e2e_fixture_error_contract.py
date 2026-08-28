import os

import api
import e2e_fixture_api
from auth_context import RequestIdentity
from e2e_fixture_api import install


install(api.APP)


def _authenticated_identity():
    account_id = os.environ["OBRASIGNAL_ACCOUNT_ID"]
    return RequestIdentity(
        account_id=account_id,
        authenticated=True,
        subject=account_id,
        claims={"sub": account_id},
    )


def test_fixture_workflow_validation_does_not_expose_exception_text(monkeypatch, tmp_path):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "tenant-a")
    monkeypatch.setenv("OBRASIGNAL_DB", str(tmp_path / "primary.db"))
    monkeypatch.setenv("OBRASIGNAL_TEST_FIXTURES_ENABLED", "1")
    monkeypatch.setenv("OBRASIGNAL_TEST_FIXTURE_DB", str(tmp_path / "fixtures.db"))
    monkeypatch.setattr(e2e_fixture_api, "configured_identity", _authenticated_identity)

    client = api.APP.test_client()
    fixture_id = client.post(
        "/api/v1/test-fixtures/opportunity", json={"run_id": "bounded-error"}
    ).get_json()["fixture_id"]

    response = client.post(
        f"/api/v1/opportunities/{fixture_id}/workflow",
        json={"status": "NOT_A_REAL_STATUS", "note": "must-not-persist"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid_workflow_request"}
