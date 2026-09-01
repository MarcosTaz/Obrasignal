from __future__ import annotations

import hashlib
from datetime import date

import pytest

from vertical_apps.industrial_claims.proof import ExternalAttestation
from vertical_apps.industrial_claims.proof_externalization import (
    ProofExternalizationError,
    build_externalized_durable_proof_pack,
)
from vertical_apps.industrial_claims.proof_providers import (
    ProofProviderBundle,
    ProofRequest,
    UnavailableProofProvider,
)
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _case(database):
    service = IndustrialClaimsService(database)
    result = service.analyze(
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
        commercial_basis_content="commercial basis",
        event_evidence_content="customer requested engineering change",
        cost_evidence_content="engineering cost record",
        notice_due=date(2026, 9, 30),
    )
    return service, result.finding.finding_id


class RecordingProvider:
    def __init__(self, kind: str, calls: list):
        self.kind = kind
        self.name = f"provider-{kind.lower()}"
        self.calls = calls

    def attest(self, request: ProofRequest):
        assert request.payload is not None
        assert hashlib.sha256(request.payload).hexdigest() == request.digest
        self.calls.append((self.kind, request))
        return ExternalAttestation(
            kind=self.kind,
            provider=self.name,
            state="VERIFIED",
            digest_algorithm=request.digest_algorithm,
            digest=request.digest,
            provider_ref=f"receipt:{self.kind}:{request.digest[:12]}",
            issued_at="2026-09-01T00:00:00+00:00",
            validation_ref=f"validation:{self.kind}:{request.digest[:12]}",
            details={"subject_ref": request.subject_ref, "purpose": request.purpose},
        )


class WrongDigestProvider(RecordingProvider):
    def attest(self, request: ProofRequest):
        item = super().attest(request)
        return ExternalAttestation(
            kind=item.kind,
            provider=item.provider,
            state="UNAVAILABLE",
            digest_algorithm=item.digest_algorithm,
            digest="f" * 64,
            details={"subject_ref": request.subject_ref, "purpose": request.purpose},
        )


def _bundle(calls):
    return ProofProviderBundle(
        qualified_timestamp=RecordingProvider("QUALIFIED_TIMESTAMP", calls),
        qualified_seal=RecordingProvider("QUALIFIED_SEAL", calls),
        qualified_signature=RecordingProvider("QUALIFIED_SIGNATURE", calls),
        worm_lock=UnavailableProofProvider(kind="WORM_LOCK"),
        public_anchor=RecordingProvider("PUBLIC_ANCHOR", calls),
        evidence_escrow=UnavailableProofProvider(kind="EVIDENCE_ESCROW"),
    )


def test_externalization_uses_one_exact_stable_target_for_all_global_providers(tmp_path):
    service, finding = _case(tmp_path / "externalize.sqlite3")
    calls = []
    result = build_externalized_durable_proof_pack(
        service,
        tenant_id="tenant-a",
        finding_id=finding,
        providers=_bundle(calls),
        generated_at="2026-09-01T00:00:00+00:00",
    )

    assert [kind for kind, _request in calls] == [
        "QUALIFIED_TIMESTAMP", "QUALIFIED_SEAL", "QUALIFIED_SIGNATURE", "PUBLIC_ANCHOR"
    ]
    payloads = {request.payload for _kind, request in calls}
    digests = {request.digest for _kind, request in calls}
    subjects = {request.subject_ref for _kind, request in calls}
    assert len(payloads) == 1
    assert len(digests) == 1
    assert len(subjects) == 1
    assert hashlib.sha256(next(iter(payloads))).hexdigest() == next(iter(digests))
    assert result["externalization"]["target_sha256"] == next(iter(digests))
    assert result["proof_manifest"]["attestation_target"]["sha256"] == next(iter(digests))
    assert result["externalization"]["global_worm_not_requested"] is True
    assert result["externalization"]["global_escrow_not_requested"] is True
    assert {item["kind"] for item in result["proof_manifest"]["external_attestations"]} == {
        "QUALIFIED_TIMESTAMP", "QUALIFIED_SEAL", "QUALIFIED_SIGNATURE", "PUBLIC_ANCHOR"
    }


def test_fail_closed_provider_bundle_does_not_fabricate_verified_external_proof(tmp_path):
    service, finding = _case(tmp_path / "fail-closed.sqlite3")
    result = build_externalized_durable_proof_pack(
        service,
        tenant_id="tenant-a",
        finding_id=finding,
        providers=ProofProviderBundle.fail_closed(),
        generated_at="2026-09-01T00:00:00+00:00",
    )
    assert set(result["externalization"]["provider_states"].values()) == {"UNAVAILABLE"}
    assert result["proof_manifest"]["required_external_gates"]["qualified_timestamp"] is True
    assert result["proof_manifest"]["required_external_gates"]["qualified_seal"] is True
    assert result["proof_manifest"]["required_external_gates"]["public_anchor"] is True


def test_even_nonverified_provider_receipt_bound_to_another_digest_is_rejected(tmp_path):
    service, finding = _case(tmp_path / "misbound.sqlite3")
    calls = []
    bundle = _bundle(calls)
    bundle = ProofProviderBundle(
        qualified_timestamp=WrongDigestProvider("QUALIFIED_TIMESTAMP", calls),
        qualified_seal=bundle.qualified_seal,
        qualified_signature=bundle.qualified_signature,
        worm_lock=bundle.worm_lock,
        public_anchor=bundle.public_anchor,
        evidence_escrow=bundle.evidence_escrow,
    )
    with pytest.raises(ProofExternalizationError, match="another digest"):
        build_externalized_durable_proof_pack(
            service,
            tenant_id="tenant-a",
            finding_id=finding,
            providers=bundle,
            generated_at="2026-09-01T00:00:00+00:00",
        )
