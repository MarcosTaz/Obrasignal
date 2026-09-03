from auth_context import RequestIdentity
from vertical_apps.industrial_claims.web import create_app


def _identity():
    return RequestIdentity(
        account_id="alpha",
        authenticated=True,
        subject="analyst",
        claims={"sub": "analyst", "roles": ["analyst"]},
    )


def test_malformed_json_returns_bounded_json_error_with_security_headers(tmp_path):
    client = create_app(tmp_path / "malformed.sqlite3", identity_resolver=_identity).test_client()

    response = client.post(
        "/analyze",
        data='{"customer_ref":',
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "invalid_json",
        "message": "request body must contain valid JSON",
    }
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_oversized_request_returns_413_json_before_domain_persistence(tmp_path):
    database = tmp_path / "oversized.sqlite3"
    client = create_app(database, identity_resolver=_identity).test_client()
    oversized = '{"customer_ref":"' + ("x" * 3_600_000) + '"}'

    response = client.post(
        "/analyze",
        data=oversized,
        content_type="application/json",
    )

    assert response.status_code == 413
    assert response.get_json() == {
        "error": "request_too_large",
        "message": "request body exceeds assisted intake limit",
    }
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
