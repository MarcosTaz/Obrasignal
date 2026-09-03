from __future__ import annotations

from typing import Any

from vertical_apps.industrial_claims.proof import ExternalAttestation, canonical_json_bytes, sha256_hex
from vertical_apps.industrial_claims.proof_extensions import semantic_diff_payload
from vertical_apps.industrial_claims.proof_providers import ProofProvider, ProofRequest


class SemanticDiffSignatureError(RuntimeError):
    pass


def build_signed_semantic_diff(
    *,
    tenant_id: str,
    finding_id: str,
    before_ref: str,
    after_ref: str,
    before_text: str,
    after_text: str,
    signature_provider: ProofProvider,
) -> dict[str, Any]:
    """Create an exact A→B textual diff and bind a signature to those exact bytes.

    Commercial/legal meaning remains a human/domain-review question. This function
    proves only the bytes/hashes/diff that the configured signature provider saw.
    """
    if getattr(signature_provider, "kind", None) != "QUALIFIED_SIGNATURE":
        raise SemanticDiffSignatureError("semantic diff requires a QUALIFIED_SIGNATURE provider")
    diff = semantic_diff_payload(
        before_ref=before_ref,
        after_ref=after_ref,
        before_text=before_text,
        after_text=after_text,
    )
    signing_body = {
        "schema": "CAUSLEDGER_SIGNED_SEMANTIC_DIFF_V1",
        "finding_id": finding_id,
        "before_ref": before_ref,
        "after_ref": after_ref,
        "before_hashes": diff["before_hashes"],
        "after_hashes": diff["after_hashes"],
        "diff_sha256": diff["diff_sha256"],
        "diff_sha512": diff["diff_sha512"],
        "interpretation": diff["interpretation"],
    }
    signing_bytes = canonical_json_bytes(signing_body)
    target_sha256 = sha256_hex(signing_bytes)
    request = ProofRequest(
        tenant_id=tenant_id,
        subject_ref=f"{finding_id}:SEMANTIC_DIFF:{before_ref}->{after_ref}",
        digest_algorithm="SHA-256",
        digest=target_sha256,
        purpose="SIGNED_SEMANTIC_REVISION_DIFF",
        metadata={
            "finding_id": finding_id,
            "before_ref": before_ref,
            "after_ref": after_ref,
            "diff_sha256": diff["diff_sha256"],
        },
        payload=signing_bytes,
    )
    attestation = signature_provider.attest(request)
    if not isinstance(attestation, ExternalAttestation):
        raise SemanticDiffSignatureError("signature provider returned an invalid attestation")
    if attestation.kind != "QUALIFIED_SIGNATURE":
        raise SemanticDiffSignatureError("signature provider returned the wrong attestation kind")
    if attestation.digest_algorithm.upper() != "SHA-256" or attestation.digest.lower() != target_sha256:
        raise SemanticDiffSignatureError("semantic diff signature is not bound to the exact signing target")
    if attestation.verified:
        details = dict(attestation.details or {})
        if str(details.get("subject_ref") or "") != request.subject_ref:
            raise SemanticDiffSignatureError("semantic diff signature subject binding mismatch")
        if str(details.get("purpose") or "") != request.purpose:
            raise SemanticDiffSignatureError("semantic diff signature purpose binding mismatch")

    return {
        "semantic_diff": diff,
        "signing_target": signing_body,
        "signing_target_sha256": target_sha256,
        "signature_attestation": attestation.as_dict(),
        "signature_verified": attestation.verified,
        "truth_boundary": {
            "proves_exact_diff_signing_target": attestation.verified,
            "does_not_establish_commercial_meaning": True,
            "does_not_establish_customer_responsibility": True,
            "does_not_establish_recoverability": True,
        },
    }
