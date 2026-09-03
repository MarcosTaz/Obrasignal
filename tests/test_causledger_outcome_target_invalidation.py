from __future__ import annotations

from auth_context import RequestIdentity
from vertical_apps.industrial_claims.web import create_app


def _identity(tenant_id: str, actor_id: str, *roles: str):
    return lambda: RequestIdentity(
        account_id=tenant_id,
        authenticated=True,
        subject=actor_id,
        claims={"sub": actor_id, "roles": list(roles)},
    )


def _candidate_payload() -> dict:
    return {
        "customer_ref": "oem-target",
        "program_ref": "program-target",
        "event_ref": "ECO-TARGET-001",
        "claim_family": "NRE",
        "commercial_basis_ref": "po-target",
        "cost_evidence_ref": "ledger-target",
        "gross_cost": "10000",
        "currency": "EUR",
        "commercial_basis_content": "synthetic signed commercial basis",
        "event_evidence_content": "synthetic customer directed engineering change",
        "cost_evidence_content": "synthetic incremental engineering cost ledger",
        "notice_deadline_not_applicable": True,
    }


def test_final_outcome_changes_proof_target_and_old_archived_receipts_are_not_reconstructed(tmp_path):
    database = tmp_path / "outcome-target-invalidation.sqlite3"
    analyst = create_app(
        database,
        identity_resolver=_identity("tenant-target", "analyst-a", "analyst"),
        allow_inline_evidence_content=True,
    ).test_client()
    reviewer = create_app(
        database,
        identity_resolver=_identity("tenant-target", "reviewer-b", "reviewer"),
        allow_inline_evidence_content=True,
    ).test_client()
    operator = create_app(
        database,
        identity_resolver=_identity("tenant-target", "operator-c", "operator"),
        allow_inline_evidence_content=True,
    ).test_client()

    created = analyst.post("/analyze", json=_candidate_payload())
    assert created.status_code == 201
    finding_id = created.get_json()["finding_id"]

    reviewed = reviewer.post(
        f"/findings/{finding_id}/review",
        json={"approved": True, "reason": "synthetic independent documentary review"},
    )
    assert reviewed.status_code == 200
    assert reviewed.get_json()["state"] == "APPROVED"
    actioned = operator.post(f"/findings/{finding_id}/action")
    assert actioned.status_code == 200
    assert actioned.get_json()["state"] == "ACTIONED"

    before = operator.get(f"/findings/{finding_id}/proof-pack")
    assert before.status_code == 200
    before_body = before.get_json()
    old_target = before_body["proof_manifest"]["attestation_target"]["sha256"]
    assert len(before_body["proof_manifest"]["evidence"]) == 3

    externalized = operator.post(
        f"/findings/{finding_id}/proof-pack/externalize",
        json={
            "confirm_external_proof_generation": True,
            "expected_target_sha256": old_target,
        },
    )
    assert externalized.status_code == 201
    operation_id = externalized.get_json()["externalization_operation"]["operation_id"]

    reconstructed_before_outcome = operator.get(f"/findings/{finding_id}/proof-pack")
    assert reconstructed_before_outcome.status_code == 200
    assert reconstructed_before_outcome.get_json()["archived_externalization"]["operation_id"] == operation_id

    recovered = operator.post(
        f"/findings/{finding_id}/resolve",
        json={
            "outcome_id": "final-payment-1",
            "recovered_amount": "7500",
            "currency": "EUR",
            "evidence_ref": "bank-settlement-target-1",
            "evidence_content": "synthetic final settlement evidence",
            "final_cumulative": True,
        },
    )
    assert recovered.status_code == 201

    after = operator.get(f"/findings/{finding_id}/proof-pack")
    assert after.status_code == 200
    after_body = after.get_json()
    new_target = after_body["proof_manifest"]["attestation_target"]["sha256"]
    assert new_target != old_target
    assert after_body["core_package"]["finding"]["state"] == "RECOVERED"
    assert len(after_body["proof_manifest"]["evidence"]) == 4
    assert "archived_externalization" not in after_body

    old_receipts = operator.get(
        f"/findings/{finding_id}/proof-pack/externalizations/{operation_id}/receipts"
    )
    assert old_receipts.status_code == 200
    assert old_receipts.get_json()["archive_chain_verified"] is True

    old_integrity = operator.get(
        f"/findings/{finding_id}/proof-pack/externalizations/{operation_id}/integrity"
    )
    assert old_integrity.status_code == 200
    assert old_integrity.get_json()["valid"] is True
    assert old_integrity.get_json()["target_sha256"] == old_target

    stale_reexternalization = operator.post(
        f"/findings/{finding_id}/proof-pack/externalize",
        json={
            "confirm_external_proof_generation": True,
            "expected_target_sha256": old_target,
        },
    )
    assert stale_reexternalization.status_code == 422
    assert "target" in stale_reexternalization.get_json()["message"].lower()
