from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from vertical_apps.industrial_claims.durable_proof import build_durable_claim_proof_pack
from vertical_apps.industrial_claims.proof import ExternalAttestation, canonical_json_bytes
from vertical_apps.industrial_claims.proof_providers import ProofProvider, ProofProviderBundle, ProofRequest
from vertical_apps.industrial_claims.service import IndustrialClaimsService


class ProofExternalizationError(RuntimeError):
    pass


def _provider_request(
    *,
    tenant_id: str,
    finding_id: str,
    revision: int,
    target: dict[str, Any],
) -> ProofRequest:
    body = target.get("body")
    if not isinstance(body, dict):
        raise ProofExternalizationError("stable proof target body is missing")
    payload = canonical_json_bytes(body)
    digest = hashlib.sha256(payload).hexdigest()
    expected = str(target.get("sha256") or "").strip().lower()
    if digest != expected:
        raise ProofExternalizationError("stable proof target SHA-256 does not match canonical target bytes")
    finding_hash = hashlib.sha256(finding_id.encode("utf-8")).hexdigest()
    return ProofRequest(
        tenant_id=tenant_id,
        subject_ref=f"causledger:proof-target:{digest}",
        digest_algorithm="SHA-256",
        digest=digest,
        purpose="CAUSLEDGER_DURABLE_PROOF_TARGET",
        metadata={
            "target_version": target.get("body", {}).get("target_version"),
            "finding_id_sha256": finding_hash,
            "revision": revision,
            "payload_is_canonical_stable_proof_target": True,
        },
        payload=payload,
    )


def _invoke(provider: ProofProvider, request: ProofRequest) -> ExternalAttestation:
    result = provider.attest(request)
    if result.kind != str(getattr(provider, "kind", "") or ""):
        raise ProofExternalizationError("proof provider returned a different attestation kind")
    if result.digest_algorithm.upper() != request.digest_algorithm.upper():
        raise ProofExternalizationError("proof provider returned a different digest algorithm")
    if result.digest.lower() != request.digest.lower():
        raise ProofExternalizationError("proof provider returned a receipt bound to another digest")
    subject = str(result.details.get("subject_ref") or "").strip()
    purpose = str(result.details.get("purpose") or "").strip()
    if result.verified and subject and subject != request.subject_ref:
        raise ProofExternalizationError("verified proof provider receipt is bound to another subject")
    if result.verified and purpose and purpose != request.purpose:
        raise ProofExternalizationError("verified proof provider receipt has another purpose")
    return result


def build_externalized_durable_proof_pack(
    service: IndustrialClaimsService,
    *,
    tenant_id: str,
    finding_id: str,
    providers: ProofProviderBundle,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Explicitly request external proof over one stable, precomputed target.

    This function is intentionally separate from the normal read-only Proof Pack.
    It never uses WORM_LOCK or EVIDENCE_ESCROW as global shortcuts: those require
    the actual individual original bytes and are handled by evidence-specific
    workflows. A target race or provider receipt substitution is a hard failure.
    """
    generated = generated_at or datetime.now(timezone.utc).isoformat()
    initial = build_durable_claim_proof_pack(
        service,
        tenant_id=tenant_id,
        finding_id=finding_id,
        generated_at=generated,
    )
    target = dict(initial["proof_manifest"]["attestation_target"])
    revision = int(initial["core_package"]["revision"]["number"])
    request = _provider_request(
        tenant_id=tenant_id,
        finding_id=finding_id,
        revision=revision,
        target=target,
    )

    provider_sequence: tuple[ProofProvider, ...] = (
        providers.qualified_timestamp,
        providers.qualified_seal,
        providers.qualified_signature,
        providers.public_anchor,
    )
    attestations = tuple(_invoke(provider, request) for provider in provider_sequence)

    final = build_durable_claim_proof_pack(
        service,
        tenant_id=tenant_id,
        finding_id=finding_id,
        attestations=attestations,
        generated_at=generated,
    )
    final_target = final["proof_manifest"]["attestation_target"]
    if final_target != target:
        raise ProofExternalizationError("durable proof target changed while external proof was being generated")
    final["externalization"] = {
        "explicit_operation": True,
        "normal_proof_pack_read_remains_side_effect_free": True,
        "target_sha256": request.digest,
        "provider_kinds_requested": [item.kind for item in attestations],
        "provider_states": {item.kind: item.state for item in attestations},
        "global_worm_not_requested": True,
        "global_escrow_not_requested": True,
        "original_evidence_requires_separate_byte-level_preservation": True,
    }
    return final
