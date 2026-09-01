from __future__ import annotations

from typing import Any

from vertical_apps.industrial_claims.durable_proof import build_durable_claim_proof_pack
from vertical_apps.industrial_claims.proof import sha256_hex
from vertical_apps.industrial_claims.proof_externalization import (
    ProofExternalizationError,
    build_externalized_durable_proof_pack,
)
from vertical_apps.industrial_claims.proof_externalization_audit import ProofExternalizationAuditStore
from vertical_apps.industrial_claims.proof_providers import ProofProviderBundle
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def externalize_proof_with_audit(
    service: IndustrialClaimsService,
    *,
    audit_store: ProofExternalizationAuditStore,
    tenant_id: str,
    finding_id: str,
    actor_id: str,
    providers: ProofProviderBundle,
    expected_target_sha256: str | None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Execute one explicit external-proof operation with durable intent/outcome lineage."""
    preflight = build_durable_claim_proof_pack(
        service,
        tenant_id=tenant_id,
        finding_id=finding_id,
        generated_at=generated_at,
    )
    target = str(preflight["proof_manifest"]["attestation_target"]["sha256"]).lower()
    if expected_target_sha256 is not None and str(expected_target_sha256).strip().lower() != target:
        raise ProofExternalizationError("reviewed proof target is stale; no external proof provider was called")

    provider_kinds = [
        providers.qualified_timestamp.kind,
        providers.qualified_seal.kind,
        providers.qualified_signature.kind,
        providers.public_anchor.kind,
    ]
    started = audit_store.start(
        tenant_id=tenant_id,
        finding_id=finding_id,
        actor_id=actor_id,
        target_sha256=target,
        payload={
            "provider_kinds": provider_kinds,
            "expected_target_sha256_enforced": expected_target_sha256 is not None,
            "normal_proof_pack_read_remains_side_effect_free": True,
        },
    )
    operation_id = str(started["operation_id"])
    try:
        pack = build_externalized_durable_proof_pack(
            service,
            tenant_id=tenant_id,
            finding_id=finding_id,
            providers=providers,
            generated_at=generated_at,
            expected_target_sha256=target,
        )
        external_attestations = list(pack["proof_manifest"].get("external_attestations") or [])
        manifest_sha256 = sha256_hex(pack["proof_manifest"])
        receipts_sha256 = sha256_hex(external_attestations)
        provider_states = dict(pack["externalization"]["provider_states"])
        verified_provider_count = sum(1 for state in provider_states.values() if state == "VERIFIED")
        all_requested_providers_verified = bool(provider_states) and verified_provider_count == len(provider_states)
        completed = audit_store.finish(
            operation_id=operation_id,
            tenant_id=tenant_id,
            finding_id=finding_id,
            actor_id=actor_id,
            state="COMPLETED",
            target_sha256=target,
            payload={
                "provider_states": provider_states,
                "verified_provider_count": verified_provider_count,
                "all_requested_providers_verified": all_requested_providers_verified,
                "operation_completed_does_not_imply_proof_verified": True,
                "proof_manifest_sha256": manifest_sha256,
                "external_attestations_sha256": receipts_sha256,
                "attestation_count": len(external_attestations),
            },
        )
        pack["externalization_operation"] = {
            "operation_id": operation_id,
            "state": "COMPLETED",
            "started_event_hash": started["event_hash"],
            "completed_event_hash": completed["event_hash"],
            "proof_manifest_sha256": manifest_sha256,
            "external_attestations_sha256": receipts_sha256,
            "verified_provider_count": verified_provider_count,
            "all_requested_providers_verified": all_requested_providers_verified,
            "operation_completed_does_not_imply_proof_verified": True,
            "audit_chain_append_only": True,
        }
        return pack
    except Exception as exc:
        audit_store.finish(
            operation_id=operation_id,
            tenant_id=tenant_id,
            finding_id=finding_id,
            actor_id=actor_id,
            state="FAILED",
            target_sha256=target,
            payload={
                "error_type": type(exc).__name__,
                "provider_failure_message_persisted": False,
            },
        )
        raise
