from types import SimpleNamespace

import api
import cors_app


class _Conn:
    def close(self):
        pass


def _authenticated(monkeypatch, account_id="verified-account"):
    identity = SimpleNamespace(account_id=account_id, authenticated=True)
    monkeypatch.setattr(api, "_identity", lambda: identity)
    monkeypatch.setattr(api, "ensure_account", lambda conn, value: None)
    monkeypatch.setattr(cors_app, "configured_identity", lambda: identity)
    monkeypatch.setattr(api, "_db", lambda: _Conn())
    return identity


def test_compare_endpoint_uses_server_identity_and_ignores_payload_account(monkeypatch):
    _authenticated(monkeypatch)
    captured = {}

    def fake_compare(conn, account_context, opportunity_ids, options=None):
        captured["account_id"] = account_context.account_id
        captured["ids"] = opportunity_ids
        return {
            "comparison_id": "cmp-test",
            "comparison_version": "opportunity-compare-v0",
            "opportunities": [],
            "dimensions": [],
            "values_by_opportunity": {},
            "missing_data": {},
            "warnings": [],
            "generated_at": "2026-08-25T00:00:00+00:00",
        }

    monkeypatch.setattr(cors_app, "compare_opportunities", fake_compare)
    client = cors_app.APP.test_client()
    response = client.post(
        "/api/v1/opportunities/compare",
        json={"opportunity_ids": [1, 2], "account_id": "attacker-account"},
    )

    assert response.status_code == 200
    assert captured == {"account_id": "verified-account", "ids": [1, 2]}
    assert response.get_json()["comparison_id"] == "cmp-test"


def test_compare_endpoint_requires_identity(monkeypatch):
    def no_identity():
        raise RuntimeError("missing identity")

    monkeypatch.setattr(api, "_identity", no_identity)
    monkeypatch.setattr(cors_app, "configured_identity", no_identity)
    client = cors_app.APP.test_client()
    response = client.post("/api/v1/opportunities/compare", json={"opportunity_ids": [1, 2]})

    assert response.status_code == 401
    assert response.get_json()["error"] == "authentication_required"


def test_compare_endpoint_rejects_non_object_json(monkeypatch):
    _authenticated(monkeypatch)
    client = cors_app.APP.test_client()

    response = client.post("/api/v1/opportunities/compare", json=[1, 2])

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_comparison"


def test_compare_endpoint_maps_domain_validation_and_not_found(monkeypatch):
    _authenticated(monkeypatch)
    client = cors_app.APP.test_client()

    monkeypatch.setattr(
        cors_app,
        "compare_opportunities",
        lambda *args, **kwargs: (_ for _ in ()).throw(cors_app.ComparisonError("bad ids")),
    )
    invalid = client.post("/api/v1/opportunities/compare", json={"opportunity_ids": [1]})
    assert invalid.status_code == 400
    assert invalid.get_json()["error"] == "invalid_comparison"

    monkeypatch.setattr(
        cors_app,
        "compare_opportunities",
        lambda *args, **kwargs: (_ for _ in ()).throw(cors_app.OpportunityNotFoundError("missing")),
    )
    missing = client.post("/api/v1/opportunities/compare", json={"opportunity_ids": [1, 99]})
    assert missing.status_code == 404
    assert missing.get_json()["error"] == "not_found"
