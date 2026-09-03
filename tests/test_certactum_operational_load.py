from auth_context import RequestIdentity
from vertical_apps.industrial_claims.web import create_app


def _identity():
    return RequestIdentity(
        account_id="tenant-load",
        authenticated=True,
        subject="reviewer-load",
        claims={"sub": "reviewer-load", "roles": ["reviewer"]},
    )


def test_repeated_tenant_scoped_queue_reads_remain_stable_and_no_store(tmp_path):
    client = create_app(tmp_path / "load.sqlite3", identity_resolver=_identity).test_client()

    for _ in range(200):
        response = client.get("/findings")
        assert response.status_code == 200
        assert response.get_json() == {
            "queue_scope": ["READY_FOR_REVIEW"],
            "count": 0,
            "findings": [],
        }
        assert response.headers["Cache-Control"] == "no-store"
