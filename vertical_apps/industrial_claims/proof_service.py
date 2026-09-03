from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from vertical_apps.industrial_claims.proof import ExternalAttestation
from vertical_apps.industrial_claims.proof_package import build_claim_proof_pack
from vertical_apps.industrial_claims.proof_providers import ProofProviderBundle, ProofRequest
from vertical_apps.industrial_claims.proof_store import IndustrialProofStore
from vertical_apps.industrial_claims.service import IndustrialClaimResult, IndustrialClaimsService


@dataclass(frozen=True)
class ProofPackResult:
    pack: dict[str, Any]
    ledger_chain_head: str | None
    external_attestations: tuple[ExternalAttestation, ...]


class CausLedgerProofService:
    """Proof orchestration without silently upgrading legal/commercial truth."""

    def __init__(self, database: str, *, providers: ProofProviderBundle | None = None) -> None:
        self.claims = IndustrialClaimsService(database)
        self.proof_store = IndustrialProofStore(database)
        self.providers = providers or ProofProviderBundle.fail_closed()

    def _request_attestations(self, *, tenant_id: str, finding_id: str, target_sha256: str) -> tuple[ExternalAttestation, ...]:
        request = ProofRequest(
            tenant_id=tenant_id,
            subject_ref=finding_id,
            digest_algorithm="SHA-256",
            digest=target_sha256,
            purpose="CAUSLEDGER_STABLE_PROOF_TARGET",
            metadata={"target_kind": "CAUSLEDGER_PROOF_TARGET_V1"},
        )
        providers = (
            self.providers.qualified_timestamp,
            self.providers.qualified_seal,
            self.providers.qualified_signature,
            self.providers.worm_lock,
            self.providers.public_anchor,
            self.providers.evidence_escrow,
        )
        return tuple(provider.attest(request) for provider in providers)

    def build_and_record_proof_pack(
        self,
        result: IndustrialClaimResult,
        *,
        customer_ref: str,
        program_ref: str,
        event_ref: str,
        actor_id: str,
        as_of_date: date | None = None,
        generated_at: str | None = None,
        request_external_attestations: bool = True,
    ) -> ProofPackResult:
        initial = build_claim_proof_pack(
            self.claims,
            result,
            customer_ref=customer_ref,
            program_ref=program_ref,
            event_ref=event_ref,
            as_of_date=as_of_date,
            generated_at=generated_at,
        )
        target_sha256 = initial["proof_manifest"]["attestation_target"]["sha256"]
        attestations: tuple[ExternalAttestation, ...] = ()
        if request_external_attestations:
            attestations = self._request_attestations(
                tenant_id=result.tenant_id,
                finding_id=result.finding.finding_id,
                target_sha256=target_sha256,
            )
            final_pack = build_claim_proof_pack(
                self.claims,
                result,
                customer_ref=customer_ref,
                program_ref=program_ref,
                event_ref=event_ref,
                as_of_date=as_of_date,
                attestations=attestations,
                generated_at=generated_at,
            )
        else:
            final_pack = initial

        manifest = final_pack["proof_manifest"]
        if manifest["attestation_target"]["sha256"] != target_sha256:
            raise ValueError("CausLedger stable proof target changed while adding attestations")
        event = self.proof_store.append_event(
            event_id=f"{result.finding.finding_id}:proof:{manifest['manifest_hashes']['sha256']}",
            tenant_id=result.tenant_id,
            subject_ref=result.finding.finding_id,
            event_type="PROOF_PACK_BUILT",
            actor_id=actor_id,
            payload={
                "manifest_sha256": manifest["manifest_hashes"]["sha256"],
                "manifest_sha512": manifest["manifest_hashes"]["sha512"],
                "attestation_target_sha256": manifest["attestation_target"]["sha256"],
                "attestation_target_sha512": manifest["attestation_target"]["sha512"],
                "package_sha256": manifest["package_hashes"]["sha256"],
                "evidence_merkle_root": manifest["evidence_merkle"]["root"],
                "external_gates": manifest["required_external_gates"],
            },
        )
        for index, attestation in enumerate(attestations):
            self.proof_store.record_attestation(
                attestation_id=f"{event.event_id}:attestation:{index}:{attestation.kind}",
                tenant_id=result.tenant_id,
                subject_ref=result.finding.finding_id,
                kind=attestation.kind,
                provider=attestation.provider,
                state=attestation.state,
                provider_ref=attestation.provider_ref,
                issued_at=attestation.issued_at,
                digest_algorithm=attestation.digest_algorithm,
                digest=attestation.digest,
                payload=attestation.as_dict(),
            )
        chain = self.proof_store.verify_chain(
            tenant_id=result.tenant_id,
            subject_ref=result.finding.finding_id,
        )
        if not chain["valid"]:
            raise ValueError("CausLedger proof ledger failed chain verification")
        return ProofPackResult(final_pack, chain["chain_head_sha256"], attestations)

    def record_fact_event(
        self,
        *,
        event_id: str,
        tenant_id: str,
        finding_id: str,
        event_type: str,
        actor_id: str,
        payload: dict[str, Any],
        source_ref: str | None = None,
        effective_at: str | None = None,
    ) -> str:
        event = self.proof_store.append_event(
            event_id=event_id,
            tenant_id=tenant_id,
            subject_ref=finding_id,
            event_type=event_type,
            actor_id=actor_id,
            payload=payload,
            source_ref=source_ref,
            effective_at=effective_at,
        )
        return event.chain_hash
