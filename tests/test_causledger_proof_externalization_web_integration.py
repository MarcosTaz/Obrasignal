from __future__ import annotations

from datetime import date

from auth_context import RequestIdentity
from vertical_apps.industrial_claims.service import IndustrialClaimsService
from vertical_apps.industrial_claims.web import create_app


def _identity(tenant_id: str, actor_id: str, *roles: str):
    return lambda: RequestIdentity(
        account_id=tenant_id,
        authenticated=True,
        subject=actor_id,
        claims={"sub": actor_id, "roles": list(roles)},
    )


def _seed_case(database) -> str:
    service = IndustrialClaimsService(database)
    return service.analyze(
        tenant_id="tenant-a",
        actor_id="analyst-a",
        customer_ref="oem-a",
        program_ref="program-a",
        event_ref="ECO-017",
        claim_family="NRE",
        commercial_basis_ref="po-1",
        cost_evidence_ref="ledger-1",
        gross_cost="10000",
        currency="EUR",
        commercial_basis_content="signed purchase order and change basis",
        event_evidence_content="documented customer-directed engineering change",
        cost_evidence_content="incremental engineering cost ledger",
        notice_due=date(2026, 9, 30),
    ).finding.finding_id


def test_app_externalization_is_operator_only_explicit_fail_closed_and_audited(tmp_path):
    database = tmp_path / "externalization-web.sqlite3"
    finding_id = _seed_case(database)

    analyst = create_app(
        database,
        identity_resolver=_identity("tenant-a", "analyst-a", "analyst"),
    ).test_client()
    forbidden = analyst.post(
        f"/findings/{finding_id}/proof-pack/externalize",
        json={"confirm_external_proof_generation": True, "expected_target_sha256": "0" * 64},
    )
    assert forbidden.status_code == 403
    assert forbidden.get_json() == {"error": "authorization_denied"}

    operator = create_app(
        database,
        identity_resolver=_identity("tenant-a", "operator-a", "operator"),
    ).test_client()

    malformed = operator.post(
        f"/findings/{finding_id}/proof-pack/externalize",
        data="{",
        content_type="application/json",
    )
    assert malformed.status_code == 400
    assert malformed.get_json()["error"] == "invalid_json"

    missing_status = operator.get("/findings/not-a-real-finding/proof-pack/externalizations")
    assert missing_status.status_code == 422

    proof = operator.get(f"/findings/{finding_id}/proof-pack")
    assert proof.status_code == 200
    target_sha256 = proof.get_json()["proof_manifest"]["attestation_target"]["sha256"]

    before = operator.get(f"/findings/{finding_id}/proof-pack/externalizations")
    assert before.status_code == 200
    assert before.get_json()["event_count"] == 0

    missing_confirmation = operator.post(
        f"/findings/{finding_id}/proof-pack/externalize",
        json={"expected_target_sha256": target_sha256},
    )
    assert missing_confirmation.status_code == 422
    assert operator.get(f"/findings/{finding_id}/proof-pack/externalizations").get_json()["event_count"] == 0

    externalized = operator.post(
        f"/findings/{finding_id}/proof-pack/externalize",
        json={
            "confirm_external_proof_generation": True,
            "expected_target_sha256": target_sha256,
        },
    )
    assert externalized.status_code == 201
    body = externalized.get_json()
    assert body["externalization"]["target_sha256"] == target_sha256
    assert body["externalization"]["provider_states"] == {
        "QUALIFIED_TIMESTAMP": "UNAVAILABLE",
        "QUALIFIED_SEAL": "UNAVAILABLE",
        "QUALIFIED_SIGNATURE": "UNAVAILABLE",
        "PUBLIC_ANCHOR": "UNAVAILABLE",
    }
    assert body["externalization"]["global_worm_not_requested"] is True
    assert body["externalization"]["global_escrow_not_requested"] is True
    operation = body["externalization_operation"]
    assert operation["state"] == "COMPLETED"
    assert operation["verified_provider_count"] == 0
    assert operation["all_requested_providers_verified"] is False
    assert operation["operation_completed_does_not_imply_proof_verified"] is True

    status = operator.get(f"/findings/{finding_id}/proof-pack/externalizations")
    assert status.status_code == 200
    status_body = status.get_json()
    assert status_body["event_count"] == 2
    events = next(iter(status_body["operations"].values()))
    assert [event["state"] for event in events] == ["STARTED", "COMPLETED"]
    assert events[-1]["payload"]["verified_provider_count"] == 0
    assert events[-1]["payload"]["all_requested_providers_verified"] is False
    assert events[-1]["payload"]["operation_completed_does_not_imply_proof_verified"] is True

    read_again = operator.get(f"/findings/{finding_id}/proof-pack")
    assert read_again.status_code == 200
    assert read_again.get_json()["proof_manifest"]["attestation_target"]["sha256"] == target_sha256
    assert operator.get(f"/findings/{finding_id}/proof-pack/externalizations").get_json()["event_count"] == 2
