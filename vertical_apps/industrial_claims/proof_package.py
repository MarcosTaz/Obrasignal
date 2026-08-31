from __future__ import annotations

from datetime import date
from typing import Any, Sequence

from vertical_apps.industrial_claims.package import build_claim_package
from vertical_apps.industrial_claims.proof import ExternalAttestation, build_proof_manifest, verify_proof_manifest
from vertical_apps.industrial_claims.service import IndustrialClaimResult, IndustrialClaimsService


def build_claim_proof_pack(
    service: IndustrialClaimsService,
    result: IndustrialClaimResult,
    *,
    customer_ref: str,
    program_ref: str,
    event_ref: str,
    as_of_date: date | None = None,
    attestations: Sequence[ExternalAttestation] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a CausLedger Proof Pack over the existing durable claim package.

    The core package remains authoritative for documentary/economic truth. The
    proof manifest authenticates package/evidence integrity and explicitly shows
    any external proof gates that are not yet satisfied. It never upgrades legal
    recoverability or factual truth by itself.
    """
    core = build_claim_package(
        service,
        result,
        customer_ref=customer_ref,
        program_ref=program_ref,
        event_ref=event_ref,
        as_of_date=as_of_date,
    )
    revision = core["revision"]
    manifest = build_proof_manifest(
        core_package=core,
        evidence=result.evidence,
        revision_number=int(revision["number"]),
        supersedes_finding_id=revision.get("supersedes_finding_id"),
        attestations=tuple(attestations),
        generated_at=generated_at,
    )
    verification = verify_proof_manifest(core, manifest)
    if not verification["valid"]:
        raise ValueError("CausLedger proof manifest failed self-verification")
    return {
        "proof_pack_schema_version": 1,
        "brand": "CausLedger",
        "core_package": core,
        "proof_manifest": manifest,
        "self_verification": verification,
        "external_verification_required": any(manifest["required_external_gates"].values()),
    }
