from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from vertical_apps.industrial_claims.proof import merkle_root_sha256, sha256_hex, sha512_hex


@dataclass(frozen=True)
class TransparencySubject:
    tenant_id: str
    subject_ref: str
    chain_head_sha256: str
    nonce: str

    def commitment(self) -> dict[str, Any]:
        if len(self.chain_head_sha256) != 64 or any(char not in "0123456789abcdef" for char in self.chain_head_sha256.lower()):
            raise ValueError("transparency chain head must be SHA-256")
        if not self.tenant_id.strip() or not self.subject_ref.strip() or len(self.nonce.strip()) < 16:
            raise ValueError("transparency subject requires tenant, subject and high-entropy nonce")
        private_body = {
            "tenant_id": self.tenant_id,
            "subject_ref": self.subject_ref,
            "chain_head_sha256": self.chain_head_sha256.lower(),
            "nonce": self.nonce,
        }
        return {
            "subject_commitment_sha256": sha256_hex(private_body),
            "subject_commitment_sha512": sha512_hex(private_body),
            "chain_head_sha256": self.chain_head_sha256.lower(),
            "private_body": private_body,
        }


def build_transparency_batch(subjects: Iterable[TransparencySubject], *, batch_id: str) -> dict[str, Any]:
    """Build a local batch whose public anchor only needs the Merkle root.

    Tenant IDs, finding IDs and nonces stay in the private batch manifest; the
    external transparency service receives only the root/leaf count unless a
    deployment explicitly chooses otherwise.
    """
    if not batch_id.strip():
        raise ValueError("transparency batch id is required")
    commitments = [subject.commitment() for subject in subjects]
    if not commitments:
        raise ValueError("transparency batch requires at least one subject")
    leaves = [item["subject_commitment_sha256"] for item in commitments]
    root = merkle_root_sha256(leaves)
    private_manifest = {
        "batch_id": batch_id,
        "leaf_count": len(commitments),
        "leaves": commitments,
        "merkle_root_sha256": root,
    }
    public_anchor_payload = {
        "proof_system": "CausLedger Transparency Log",
        "batch_id": batch_id,
        "leaf_count": len(commitments),
        "merkle_root_sha256": root,
        "contains_customer_or_tenant_identifiers": False,
    }
    return {
        "private_manifest": private_manifest,
        "private_manifest_sha256": sha256_hex(private_manifest),
        "public_anchor_payload": public_anchor_payload,
        "public_anchor_payload_sha256": sha256_hex(public_anchor_payload),
        "public_anchor_payload_sha512": sha512_hex(public_anchor_payload),
    }
