from __future__ import annotations

from auth_context import RequestIdentity
from vertical_apps.industrial_claims.web import create_app as _create_app


def create_app(*args, **kwargs):
    kwargs.setdefault("allow_inline_evidence_content", True)
    return _create_app(*args, **kwargs)


def _identity(tenant_id: str, actor_id: str, *roles: str):
    return lambda: RequestIdentity(
        account_id=tenant_id,
        authenticated=True,
        subject=actor_id,
        claims={"sub": actor_id, "roles": list(roles)},
    )


def _payload(**overrides):
    payload = {
        "customer_ref": "oem-history",
        "program_ref": "program-history",
        "event_ref": "ECO-HISTORY-001",
        "claim_family": "NRE",
        "commercial_basis_ref": "po-history",
        "cost_evidence_ref": "ledger-v1",
        "gross_cost": "10000",
        "currency": "EUR",
        "commercial_basis_content": "signed purchase order and engineering-change basis",
        "event_evidence_content": "documented customer-directed engineering change",
        "cost_evidence_content": "incremental engineering cost ledger version one",
        "notice_deadline_not_applicable": True,
    }
    payload.update(overrides)
    return payload


def test_superseded_revision_keeps_old_receipts_but_cannot_be_externalized_again(tmp_path):
    database = tmp_path / "proof-supersession.sqlite3"
    analyst = create_app(
        database,
        identity_resolver=_identity("tenant-history", "analyst-history", "analyst"),
    ).test_client()
    operator = create_app(
        database,
        identity_resolver=_identity("tenant-history", "operator-history", "operator"),
    ).test_client()

    created = analyst.post("/analyze", json=_payload())
    assert created.status_code == 201
    first_id = created.get_json()["finding_id"]

    proof = operator.get(f"/findings/{first_id}/proof-pack")
    assert proof.status_code == 200
    target_sha256 = proof.get_json()["proof_manifest"]["attestation_target"]["sha256"]

    externalized = operator.post(
        f"/findings/{first_id}/proof-pack/externalize",
        json={
            "confirm_external_proof_generation": True,
            "expected_target_sha256": target_sha256,
        },
    )
    assert externalized.status_code == 201
    operation = externalized.get_json()["externalization_operation"]
    operation_id = operation["operation_id"]
    assert operation["receipts_durably_archived"] is True
    assert operation["attestation_archive_receipt_count"] == 4

    before_amendment = operator.get(f"/findings/{first_id}/proof-pack/externalizations")
    assert before_amendment.status_code == 200
    assert before_amendment.get_json()["event_count"] == 2

    amended = analyst.post(
        f"/findings/{first_id}/amend",
        json=_payload(
            cost_evidence_ref="ledger-v2",
            gross_cost="12000",
            cost_evidence_content="corrected incremental engineering cost ledger version two",
        ),
    )
    assert amended.status_code == 201
    second_id = amended.get_json()["finding_id"]
    assert second_id != first_id
    assert amended.get_json()["revision"] == 2
    assert amended.get_json()["supersedes_finding_id"] == first_id

    old_status = operator.get(f"/findings/{first_id}/proof-pack/externalizations")
    assert old_status.status_code == 200
    assert old_status.get_json()["event_count"] == 2

    old_receipts = operator.get(
        f"/findings/{first_id}/proof-pack/externalizations/{operation_id}/receipts"
    )
    assert old_receipts.status_code == 200
    receipts_body = old_receipts.get_json()
    assert receipts_body["archive_chain_verified"] is True
    assert receipts_body["receipt_count"] == 4
    assert receipts_body["receipts_sha256"] == operation["external_attestations_sha256"]

    old_integrity = operator.get(
        f"/findings/{first_id}/proof-pack/externalizations/{operation_id}/integrity"
    )
    assert old_integrity.status_code == 200
    integrity_body = old_integrity.get_json()
    assert integrity_body["valid"] is True
    assert integrity_body["operation_state"] == "COMPLETED"
    assert integrity_body["target_sha256"] == target_sha256
    assert integrity_body["operation_archive_chain_head_sha256"] == operation["attestation_archive_chain_head_sha256"]

    blocked = operator.post(
        f"/findings/{first_id}/proof-pack/externalize",
        json={
            "confirm_external_proof_generation": True,
            "expected_target_sha256": target_sha256,
        },
    )
    assert blocked.status_code == 422
    assert "superseded" in blocked.get_json()["message"]
    assert operator.get(f"/findings/{first_id}/proof-pack/externalizations").get_json()["event_count"] == 2

    current_status = operator.get(f"/findings/{second_id}/proof-pack/externalizations")
    assert current_status.status_code == 200
    assert current_status.get_json()["event_count"] == 0

    wrong_revision = operator.get(
        f"/findings/{second_id}/proof-pack/externalizations/{operation_id}/receipts"
    )
    assert wrong_revision.status_code == 422
    assert "does not belong" in wrong_revision.get_json()["message"]

    wrong_revision_integrity = operator.get(
        f"/findings/{second_id}/proof-pack/externalizations/{operation_id}/integrity"
    )
    assert wrong_revision_integrity.status_code == 422
    assert "does not belong" in wrong_revision_integrity.get_json()["message"]
