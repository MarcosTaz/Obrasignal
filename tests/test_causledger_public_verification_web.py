from __future__ import annotations

from flask import Flask

import vertical_apps.industrial_claims.public_verification_web as public_web
from vertical_apps.industrial_claims.proof import build_proof_manifest, verify_proof_manifest
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.public_verification_store import PublicVerificationStore


class Evidence:
    evidence_id = "private:e1"
    source_type = "email"
    source_ref = "private-message-id"
    received_at = "2026-08-31T22:00:00+00:00"
    _digests = dual_digest(b"private evidence")
    content_hash = _digests["sha256"]
    metadata = {
        "content_sha512": _digests["sha512"],
        "content_size_bytes": _digests["byte_length"],
        "raw_content_persisted": "false",
        "source_authentication": "UNVERIFIED",
        "time_attestation": "LOCAL_SERVER_ONLY",
        "immutability": "NOT_PROVEN",
    }


def _pack():
    core = {
        "tenant_id": "private-tenant",
        "finding": {"finding_id": "private:finding"},
        "customer_ref": "Private Customer",
        "net_potential": "123456",
    }
    manifest = build_proof_manifest(
        core_package=core,
        evidence=(Evidence(),),
        revision_number=1,
        supersedes_finding_id=None,
        generated_at="2026-08-31T22:05:00+00:00",
    )
    verification = verify_proof_manifest(core, manifest)
    return {
        "proof_manifest": manifest,
        "self_verification": verification,
        "external_verification_required": True,
    }


def _app(tmp_path, monkeypatch):
    database = tmp_path / "proof.db"
    store = PublicVerificationStore(database)
    identity = {"tenant": "tenant-a", "actor": "operator-a"}
    monkeypatch.setattr(public_web, "build_durable_claim_proof_pack", lambda *args, **kwargs: _pack())
    app = Flask(__name__)
    app.register_blueprint(public_web.create_public_verification_blueprint(
        service=object(),
        store=store,
        publication_identity=lambda: (identity["tenant"], identity["actor"]),
    ))
    return app, identity


def test_publication_requires_explicit_confirmation_and_public_lookup_leaks_no_case_data(tmp_path, monkeypatch):
    app, _identity = _app(tmp_path, monkeypatch)
    client = app.test_client()
    rejected = client.post("/findings/private:finding/public-verification", json={})
    assert rejected.status_code == 422

    response = client.post(
        "/findings/private:finding/public-verification",
        json={"confirm_publication": True},
    )
    assert response.status_code == 201
    token = response.get_json()["verification_id"]
    public = client.get(f"/verify/{token}")
    assert public.status_code == 200
    rendered = repr(public.get_json())
    assert "private-tenant" not in rendered
    assert "private:finding" not in rendered
    assert "Private Customer" not in rendered
    assert "123456" not in rendered
    assert "private-message-id" not in rendered


def test_other_tenant_cannot_withdraw_public_receipt_even_with_token(tmp_path, monkeypatch):
    app, identity = _app(tmp_path, monkeypatch)
    client = app.test_client()
    issued = client.post(
        "/findings/f1/public-verification",
        json={"confirm_publication": True},
    ).get_json()
    token = issued["verification_id"]
    identity["tenant"] = "tenant-b"
    identity["actor"] = "operator-b"
    response = client.post(
        f"/verify/{token}/withdraw",
        json={"confirm_withdrawal": True, "reason": "unauthorized attempt"},
    )
    assert response.status_code == 422
    assert "does not belong" in response.get_json()["message"]
    assert client.get(f"/verify/{token}").get_json()["current_lifecycle"]["state"] == "CURRENT"


def test_unknown_public_token_returns_generic_404(tmp_path, monkeypatch):
    app, _identity = _app(tmp_path, monkeypatch)
    response = app.test_client().get("/verify/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
    assert response.status_code == 404
    assert response.get_json() == {"error": "verification_not_found"}
