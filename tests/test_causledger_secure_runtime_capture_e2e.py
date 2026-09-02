from __future__ import annotations

import base64

from auth_context import RequestIdentity
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalObjectReceipt
from vertical_apps.industrial_claims.web import create_app


class Store:
    name = "fake-compliance-worm"

    def __init__(self):
        self._stored: dict[tuple[str, str], bytes] = {}
        self.put_calls = 0

    def put_immutable(self, *, tenant_id, evidence_id, content, content_type, retention_until, legal_hold, metadata):
        self.put_calls += 1
        object_ref = f"{tenant_id}/{evidence_id}"
        version_ref = "v1"
        key = (object_ref, version_ref)
        existing = self._stored.get(key)
        if existing is not None and existing != content:
            raise ValueError("immutable object collision")
        self._stored[key] = content
        digests = dual_digest(content)
        return OriginalObjectReceipt(
            provider=self.name,
            object_ref=object_ref,
            version_ref=version_ref,
            sha256=digests["sha256"],
            sha512=digests["sha512"],
            byte_length=digests["byte_length"],
            retention_mode="COMPLIANCE",
            retention_until=retention_until,
            legal_hold=False,
            provider_receipt_ref=f"receipt-{evidence_id}",
            metadata=dict(metadata),
        )

    def read_immutable_version(self, *, tenant_id, evidence_id, object_ref, version_ref):
        return self._stored[(object_ref, version_ref)]


def _identity(actor_id: str, *roles: str):
    return lambda: RequestIdentity(
        account_id="tenant-a",
        authenticated=True,
        subject=actor_id,
        claims={"sub": actor_id, "roles": list(roles)},
    )


def _case_authorization() -> dict:
    return {
        "authorization_id": "runtime-case-auth-1",
        "case_ref": "runtime-case-1",
        "authorized_by_ref": "synthetic-controller@example.test",
        "authorized_at": "2026-09-01T00:00:00+00:00",
        "expires_at": "2026-09-03T00:00:00+00:00",
        "minimum_immutable_retention_until": "2027-09-03T00:00:00+00:00",
        "transfer_channel_ref": "synthetic-secure-channel",
        "evidence_roles": ["commercial_basis", "event", "cost"],
        "data_terms_state": "SIGNED",
        "immutable_retention_acknowledged": True,
        "max_bytes_per_evidence": 1_000_000,
    }


def _outcome_authorization() -> dict:
    return {
        "authorization_id": "runtime-outcome-auth-1",
        "authorized_by_ref": "synthetic-controller@example.test",
        "authorized_at": "2026-09-01T00:00:00+00:00",
        "expires_at": "2026-09-03T00:00:00+00:00",
        "minimum_immutable_retention_until": "2027-09-03T00:00:00+00:00",
        "transfer_channel_ref": "synthetic-secure-outcome-channel",
        "data_terms_state": "SIGNED",
        "immutable_retention_acknowledged": True,
        "max_bytes": 1_000_000,
    }


def _capture_payload(*, role: str, evidence_id: str, source_ref: str, content: bytes) -> dict:
    return {
        "authorization": _case_authorization(),
        "evidence_role": role,
        "evidence_id": evidence_id,
        "source_ref": source_ref,
        "content_type": "application/pdf",
        "content_base64": base64.b64encode(content).decode("ascii"),
    }


def _outcome_capture_payload(*, evidence_id: str, source_ref: str, content: bytes) -> dict:
    return {
        "authorization": _outcome_authorization(),
        "evidence_id": evidence_id,
        "source_ref": source_ref,
        "content_type": "application/pdf",
        "content_base64": base64.b64encode(content).decode("ascii"),
    }


def test_authorized_runtime_capture_to_recovered_offline_dossier_e2e(tmp_path):
    database = tmp_path / "secure-runtime-e2e.sqlite3"
    store = Store()
    operator = create_app(
        database,
        identity_resolver=_identity("operator-a", "operator"),
        original_evidence_store=store,
    ).test_client()
    analyst = create_app(
        database,
        identity_resolver=_identity("analyst-a", "analyst"),
        original_evidence_store=store,
    ).test_client()
    reviewer = create_app(
        database,
        identity_resolver=_identity("reviewer-a", "reviewer"),
        original_evidence_store=store,
    ).test_client()

    denied = analyst.post(
        "/secure-evidence/capture",
        json=_capture_payload(
            role="commercial_basis",
            evidence_id="tenant-a:runtime-case-1:denied",
            source_ref="po-denied",
            content=b"must not be written",
        ),
    )
    assert denied.status_code == 403
    assert denied.get_json() == {"error": "authorization_denied"}
    assert store._stored == {}
    assert store.put_calls == 0

    originals = {
        "commercial_basis": b"SYNTHETIC SIGNED PURCHASE ORDER BASIS",
        "event": b"SYNTHETIC CUSTOMER DIRECTED ENGINEERING CHANGE",
        "cost": b"SYNTHETIC INCREMENTAL COST LEDGER",
    }
    refs = {
        "commercial_basis": "po-runtime-1",
        "event": "change-runtime-1",
        "cost": "ledger-runtime-1",
    }
    evidence_ids = {
        role: f"tenant-a:runtime-case-1:{role}"
        for role in originals
    }
    for role in ("commercial_basis", "event", "cost"):
        response = operator.post(
            "/secure-evidence/capture",
            json=_capture_payload(
                role=role,
                evidence_id=evidence_ids[role],
                source_ref=refs[role],
                content=originals[role],
            ),
        )
        assert response.status_code == 201
        body = response.get_json()
        assert body["evidence_id"] == evidence_ids[role]
        assert body["evidence_role"] == role
        assert body["source_authentication"] == "UNVERIFIED"
        assert body["source_authenticity_established"] is False
        assert body["authorization_identity_independently_verified"] is False
        assert body["recoverability_established"] is False
        assert body["exact_version_readback_verified"] is True
        assert body["raw_content_persisted"] is True
        assert body["raw_content_returned"] is False
        assert body["idempotent_replay"] is False
        assert "content_base64" not in body
        assert "authorized_by_ref" not in body
    assert store.put_calls == 3

    replay_payload = _capture_payload(
        role="event",
        evidence_id=evidence_ids["event"],
        source_ref=refs["event"],
        content=originals["event"],
    )
    replay = operator.post("/secure-evidence/capture", json=replay_payload)
    assert replay.status_code == 200
    assert replay.get_json()["idempotent_replay"] is True
    assert store.put_calls == 3

    changed_effective_at = dict(replay_payload)
    changed_effective_at["effective_at"] = "2026-09-01T12:00:00+00:00"
    effective_collision = operator.post("/secure-evidence/capture", json=changed_effective_at)
    assert effective_collision.status_code == 422
    assert store.put_calls == 3

    changed_bytes = dict(replay_payload)
    changed_bytes["content_base64"] = base64.b64encode(b"DIFFERENT EVENT BYTES").decode("ascii")
    collision = operator.post("/secure-evidence/capture", json=changed_bytes)
    assert collision.status_code == 422
    assert "collision" in collision.get_json()["message"]
    assert store.put_calls == 3

    changed_source = dict(replay_payload)
    changed_source["source_ref"] = "change-runtime-other"
    source_collision = operator.post("/secure-evidence/capture", json=changed_source)
    assert source_collision.status_code == 422
    assert "source reference" in source_collision.get_json()["message"]
    assert store.put_calls == 3

    created = analyst.post(
        "/secure-analyze",
        json={
            "intake_case_ref": "runtime-case-1",
            "evidence_ids": evidence_ids,
            "customer_ref": "oem-runtime",
            "program_ref": "program-runtime",
            "event_ref": refs["event"],
            "claim_family": "NRE",
            "commercial_basis_ref": refs["commercial_basis"],
            "cost_evidence_ref": refs["cost"],
            "gross_cost": "10000",
            "currency": "EUR",
            "notice_deadline_not_applicable": True,
        },
    )
    assert created.status_code == 201
    finding_id = created.get_json()["finding_id"]
    assert created.get_json()["evidence_custody_state"] == "AUTHORIZED_IMMUTABLE_ORIGINALS"
    assert set(created.get_json()["source_authentication_states"].values()) == {"UNVERIFIED"}

    reviewed = reviewer.post(
        f"/findings/{finding_id}/review",
        json={"approved": True, "reason": "synthetic independent documentary review"},
    )
    assert reviewed.status_code == 200
    assert reviewed.get_json()["state"] == "APPROVED"
    actioned = operator.post(f"/findings/{finding_id}/action", json={})
    assert actioned.status_code == 200
    assert actioned.get_json()["state"] == "ACTIONED"

    outcome_bytes = b"SYNTHETIC FINAL SETTLEMENT PAYMENT EVIDENCE"
    outcome_evidence_id = "tenant-a:runtime-case-1:outcome:payment-1"
    outcome_payload = _outcome_capture_payload(
        evidence_id=outcome_evidence_id,
        source_ref="bank-runtime-1",
        content=outcome_bytes,
    )
    outcome_captured = operator.post(
        f"/findings/{finding_id}/secure-outcome-evidence/capture",
        json=outcome_payload,
    )
    assert outcome_captured.status_code == 201
    outcome_capture_body = outcome_captured.get_json()
    assert outcome_capture_body["evidence_id"] == outcome_evidence_id
    assert outcome_capture_body["source_authentication"] == "UNVERIFIED"
    assert outcome_capture_body["raw_content_returned"] is False
    assert outcome_capture_body["idempotent_replay"] is False
    assert store.put_calls == 4

    outcome_replay = operator.post(
        f"/findings/{finding_id}/secure-outcome-evidence/capture",
        json=outcome_payload,
    )
    assert outcome_replay.status_code == 200
    assert outcome_replay.get_json()["idempotent_replay"] is True
    assert store.put_calls == 4

    changed_outcome_effective_at = dict(outcome_payload)
    changed_outcome_effective_at["effective_at"] = "2026-09-01T12:00:00+00:00"
    outcome_effective_collision = operator.post(
        f"/findings/{finding_id}/secure-outcome-evidence/capture",
        json=changed_outcome_effective_at,
    )
    assert outcome_effective_collision.status_code == 422
    assert store.put_calls == 4

    changed_outcome_source = dict(outcome_payload)
    changed_outcome_source["source_ref"] = "bank-runtime-other"
    outcome_collision = operator.post(
        f"/findings/{finding_id}/secure-outcome-evidence/capture",
        json=changed_outcome_source,
    )
    assert outcome_collision.status_code == 422
    assert "source reference" in outcome_collision.get_json()["message"]
    assert store.put_calls == 4

    changed_outcome_bytes = dict(outcome_payload)
    changed_outcome_bytes["content_base64"] = base64.b64encode(b"DIFFERENT SETTLEMENT BYTES").decode("ascii")
    outcome_bytes_collision = operator.post(
        f"/findings/{finding_id}/secure-outcome-evidence/capture",
        json=changed_outcome_bytes,
    )
    assert outcome_bytes_collision.status_code == 422
    assert "collision" in outcome_bytes_collision.get_json()["message"]
    assert store.put_calls == 4

    resolved = operator.post(
        f"/findings/{finding_id}/secure-resolve",
        json={
            "outcome_id": "payment-1",
            "recovered_amount": "7500",
            "currency": "EUR",
            "evidence_id": outcome_evidence_id,
            "evidence_ref": "bank-runtime-1",
            "final_cumulative": True,
        },
    )
    assert resolved.status_code == 201
    assert resolved.get_json()["state"] == "RECOVERED"
    assert resolved.get_json()["source_authentication_state"] == "UNVERIFIED"

    proof = reviewer.get(f"/findings/{finding_id}/proof-pack")
    assert proof.status_code == 200
    proof_body = proof.get_json()
    assert proof_body["core_package"]["finding"]["state"] == "RECOVERED"
    manifest_ids = {item["evidence_id"] for item in proof_body["proof_manifest"]["evidence"]}
    assert manifest_ids == set(evidence_ids.values()) | {outcome_evidence_id}
    assert proof_body["core_package"]["truth_boundaries"]["secure_authorization_scope_recomputed_from_persisted_metadata"] is True
    target = proof_body["proof_manifest"]["attestation_target"]["sha256"]

    exported = operator.post(
        f"/findings/{finding_id}/proof-pack/offline-export",
        json={
            "confirm_confidential_export": True,
            "expected_target_sha256": target,
        },
    )
    assert exported.status_code == 200
    bundle = exported.get_json()
    assert bundle["independent_verification"]["valid"] is True
    exported_ids = set(bundle["offline_evidence"])
    assert exported_ids == manifest_ids
    assert base64.b64decode(bundle["offline_evidence"][outcome_evidence_id]["content_base64"]) == outcome_bytes
    for role, evidence_id in evidence_ids.items():
        assert base64.b64decode(bundle["offline_evidence"][evidence_id]["content_base64"]) == originals[role]
