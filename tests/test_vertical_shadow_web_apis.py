from factory_cloud.trusted_upstream_identity import TrustedUpstreamVerifier, signed_test_headers

SECRET = "s" * 32
NOW = 1_800_000_000
VERIFIER = TrustedUpstreamVerifier(SECRET, clock=lambda: NOW)


def _headers(tenant="shadow-tenant", actor="shadow-analyst", *, path="/shadow/analyze"):
    return signed_test_headers(
        secret=SECRET, tenant_id=tenant, actor_id=actor,
        method="POST", path=path, timestamp=NOW,
    )


def _evidence(ref, digit):
    return {
        "source_ref": ref,
        "sha256": digit * 64,
        "provenance": "reconstructed_public_case",
        "authorized": True,
    }


def test_contractcredit_shadow_endpoint_is_evidence_backed_and_fail_closed(tmp_path):
    from vertical_apps.contractcredit.web import create_app

    client = create_app(tmp_path / "credit.sqlite3", identity_resolver=VERIFIER.verify_request).test_client()
    payload = {
        "service_contract": _evidence("public-msa.pdf", "a"),
        "incident_evidence": _evidence("public-incident.pdf", "b"),
        "monthly_fee": "50000",
        "credit_rate": "0.10",
        "notice_due": "2026-09-15",
    }
    response = client.post("/shadow/analyze", headers=_headers(), json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data["potential_value"] == "5000.00"
    assert data["pilot_state"] == "CANDIDATE_READY_FOR_HUMAN_REVIEW"
    assert data["breach_state"] == "NOT_ESTABLISHED"
    assert data["entitlement_state"] == "UNKNOWN"
    assert data["recovery_state"] == "NOT_ESTABLISHED"

    payload["service_contract"]["authorized"] = False
    rejected = client.post("/shadow/analyze", headers=_headers(), json=payload)
    assert rejected.status_code == 422
    assert "not authorized" in rejected.get_json()["message"]


def test_aviation_shadow_endpoint_is_evidence_backed_and_fail_closed(tmp_path):
    from vertical_apps.aviation_recovery.web import create_app

    client = create_app(tmp_path / "aviation.sqlite3", identity_resolver=VERIFIER.verify_request).test_client()
    payload = {
        "lease_contract": _evidence("public-lease.pdf", "c"),
        "maintenance_event": _evidence("public-shop.pdf", "d"),
        "eligible_cost": "100000",
        "reimbursed_amount": "25000",
        "notice_due": "2026-09-30",
    }
    response = client.post("/shadow/analyze", headers=_headers(), json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data["potential_value"] == "75000"
    assert data["pilot_state"] == "CANDIDATE_READY_FOR_HUMAN_REVIEW"
    assert data["entitlement_state"] == "UNKNOWN"
    assert data["recovery_state"] == "NOT_ESTABLISHED"

    payload["maintenance_event"]["sha256"] = "bad"
    rejected = client.post("/shadow/analyze", headers=_headers(), json=payload)
    assert rejected.status_code == 422
    assert "64-character hexadecimal digest" in rejected.get_json()["message"]


def test_shadow_endpoints_reject_unsigned_identity(tmp_path):
    from vertical_apps.contractcredit.web import create_app as create_credit
    from vertical_apps.aviation_recovery.web import create_app as create_aviation

    for create_app, filename in ((create_credit, "credit.sqlite3"), (create_aviation, "aviation.sqlite3")):
        client = create_app(tmp_path / filename, identity_resolver=VERIFIER.verify_request).test_client()
        response = client.post("/shadow/analyze", headers={"X-Tenant-ID": "shadow", "X-Actor-ID": "analyst"}, json={})
        assert response.status_code == 422
        assert "timestamp" in response.get_json()["message"] or "signature" in response.get_json()["message"]
