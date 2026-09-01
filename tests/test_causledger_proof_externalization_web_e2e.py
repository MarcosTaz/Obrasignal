from __future__ import annotations

from auth_context import RequestIdentity
from vertical_apps.industrial_claims.proof import ExternalAttestation
from vertical_apps.industrial_claims.proof_providers import (
    ProofProviderBundle,
    ProofRequest,
    UnavailableProofProvider,
)
from vertical_apps.industrial_claims.service import IndustrialClaimsService
from vertical_apps.industrial_claims.web import create_app


class RecordingProvider:
    def __init__(self, kind: str, calls: list[str]):
        self.kind = kind
        self.name = f"recording-{kind.lower()}"
        self.calls = calls

    def attest(self, request: ProofRequest) -> ExternalAttestation:
        self.calls.append(self.kind)
        return ExternalAttestation(
            kind=self.kind,
            provider=self.name,
            state="VERIFIED",
            digest_algorithm=request.digest_algorithm,
            digest=request.digest,
            provider_ref=f"receipt:{self.kind}",
            issued_at="2026-09-01T12:00:00+00:00",
            validation_ref=f"validation:{self.kind}",
            details={
                "subject_ref": request.subject_ref,
                "purpose": request.purpose,
            },
        )


def _bundle(calls: list[str]) -> ProofProviderBundle:
    return ProofProviderBundle(
        qualified_timestamp=RecordingProvider("QUALIFIED_TIMESTAMP", calls),
        qualified_seal=RecordingProvider("QUALIFIED_SEAL", calls),
        qualified_signature=RecordingProvider("QUALIFIED_SIGNATURE", calls),
        worm_lock=UnavailableProofProvider(kind="WORM_LOCK"),
        public_anchor=RecordingProvider("PUBLIC_ANCHOR", calls),
        evidence_escrow=UnavailableProofProvider(kind="EVIDENCE_ESCROW"),
    )


def _identity(role: str) -> RequestIdentity:
    return RequestIdentity(
        account_id="tenant-a",
        authenticated=True,
        subject=f"{role}-a",
        claims={"roles": [role]},
    )


def _case(database):
    service = IndustrialClaimsService(database)
    result = service.analyze(
        tenant_id="tenant-a",
        actor_id="analyst-a",
        customer_ref="customer-1",
        program_ref="program-1",
        event_ref="change-R17",
        claim_family="NRE",
        commercial_basis_ref="po-1",
        cost_evidence_ref="timesheet-1",
        gross_cost="5000",
        currency="EUR",
        commercial_basis_content="Commercial basis",
        event_evidence_content="Customer requested change R17",
        cost_evidence_content="Engineering cost support",
        notice_deadline_not_applicable=True,
    )
    return result.finding.finding_id


def test_http_externalization_is_operator_only_target_locked_and_read_side_effect_free(tmp_path):
    database = tmp_path / "claims.db"
    finding_id = _case(database)
    calls: list[str] = []
    current_identity = {"value": _identity("analyst")}
    app = create_app(
        database,
        identity_resolver=lambda: current_identity["value"],
        proof_providers=_bundle(calls),
    )
    client = app.test_client()

    # Normal Proof Pack reads are allowed for analysts and remain strictly read-only.
    read_response = client.get(f"/findings/{finding_id}/proof-pack")
    assert read_response.status_code == 200
    target_sha = read_response.get_json()["proof_manifest"]["attestation_target"]["sha256"]
    assert calls == []

    # Analysts cannot trigger the external effect endpoint at all.
    denied = client.post(
        f"/findings/{finding_id}/proof-pack/externalize",
        json={
            "confirm_external_proof_generation": True,
            "expected_target_sha256": target_sha,
        },
    )
    assert denied.status_code == 403
    assert calls == []

    current_identity["value"] = _identity("operator")

    initial_status = client.get(f"/findings/{finding_id}/proof-pack/externalizations")
    assert initial_status.status_code == 200
    assert initial_status.get_json()["event_count"] == 0

    # Explicit confirmation is mandatory and rejection creates no audit event/provider call.
    unconfirmed = client.post(
        f"/findings/{finding_id}/proof-pack/externalize",
        json={
            "confirm_external_proof_generation": False,
            "expected_target_sha256": target_sha,
        },
    )
    assert unconfirmed.status_code == 422
    assert calls == []
    assert client.get(f"/findings/{finding_id}/proof-pack/externalizations").get_json()["event_count"] == 0

    # Optimistic target locking fails before STARTED and before any provider invocation.
    stale = client.post(
        f"/findings/{finding_id}/proof-pack/externalize",
        json={
            "confirm_external_proof_generation": True,
            "expected_target_sha256": "f" * 64,
        },
    )
    assert stale.status_code == 422
    assert calls == []
    assert client.get(f"/findings/{finding_id}/proof-pack/externalizations").get_json()["event_count"] == 0

    success = client.post(
        f"/findings/{finding_id}/proof-pack/externalize",
        json={
            "confirm_external_proof_generation": True,
            "expected_target_sha256": target_sha,
        },
    )
    assert success.status_code == 201
    payload = success.get_json()
    assert payload["externalization"]["target_sha256"] == target_sha
    assert payload["externalization_operation"]["target_sha256"] == target_sha
    assert calls == [
        "QUALIFIED_TIMESTAMP",
        "QUALIFIED_SEAL",
        "QUALIFIED_SIGNATURE",
        "PUBLIC_ANCHOR",
    ]

    status = client.get(f"/findings/{finding_id}/proof-pack/externalizations")
    assert status.status_code == 200
    status_payload = status.get_json()
    assert status_payload["event_count"] == 2
    events = next(iter(status_payload["operations"].values()))
    assert [event["state"] for event in events] == ["STARTED", "COMPLETED"]

    # A later normal read must still be side-effect free.
    calls_before_read = list(calls)
    event_count_before_read = status_payload["event_count"]
    reread = client.get(f"/findings/{finding_id}/proof-pack")
    assert reread.status_code == 200
    assert calls == calls_before_read
    assert client.get(f"/findings/{finding_id}/proof-pack/externalizations").get_json()["event_count"] == event_count_before_read
