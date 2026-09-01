from __future__ import annotations

from vertical_apps.industrial_claims.proof_readiness import evaluate_proof_strength
from vertical_apps.industrial_claims.proof_trust_policy import evaluate_provider_independence


EVIDENCE_SHA = "c" * 64


def _attestation(
    kind: str,
    provider: str,
    *,
    validation: bool = True,
    evidence_id: str | None = None,
    verified_original_escrow: bool = False,
):
    details = {}
    if evidence_id is not None:
        details["evidence_id"] = evidence_id
    if verified_original_escrow:
        details.update({
            "binding_verified": True,
            "original_bytes_escrowed": True,
            "read_back_verified": True,
        })
    return {
        "kind": kind,
        "provider": provider,
        "state": "VERIFIED",
        "digest_algorithm": "SHA-256",
        "digest": EVIDENCE_SHA if kind == "EVIDENCE_ESCROW" else "d" * 64,
        "provider_ref": f"{provider}:{kind}:1",
        "validation_ref": f"{provider}:validation:1" if validation else None,
        "issued_at": "2026-08-31T23:00:00+00:00" if validation else None,
        "details": details,
    }


def _manifest(external, *, original_integrity_sealed: bool = True):
    external = list(external)
    per_evidence = [
        item
        for item in external
        if item.get("kind") == "EVIDENCE_ESCROW"
        and (item.get("details") or {}).get("evidence_id") == "ev-1"
    ]
    return {
        "manifest_hashes": {"sha256": "a" * 64},
        "attestation_target": {"sha256": "b" * 64},
        "dual_hash_coverage": {"sha256": True, "sha512": True},
        "evidence": [
            {
                "evidence_id": "ev-1",
                "hashes": {"sha256": EVIDENCE_SHA, "sha512": "e" * 128},
                "raw_content_persisted": True,
                "immutability": "WORM_LOCKED",
                "assurance_dimensions": {
                    "source_authenticated": True,
                    "integrity_sealed": original_integrity_sealed,
                },
                "external_attestations": per_evidence,
            }
        ],
        "external_attestations": external,
    }


def test_one_provider_cannot_create_independent_witness_strength():
    external = [
        _attestation("WORM_LOCK", "provider-a", validation=False),
        _attestation("QUALIFIED_TIMESTAMP", "provider-a"),
        _attestation("QUALIFIED_SEAL", "provider-a"),
        _attestation("PUBLIC_ANCHOR", "provider-a", validation=False),
        _attestation(
            "EVIDENCE_ESCROW",
            "provider-a",
            validation=False,
            evidence_id="ev-1",
            verified_original_escrow=True,
        ),
    ]
    independence = evaluate_provider_independence(_manifest(external))
    assert independence["public_anchor_independent_from_qualified_provider"] is False
    assert independence["provider_quorum_at_least_two"] is False
    assert evaluate_proof_strength(_manifest(external))["level"] == "QUALIFIED_ORIGIN_VERIFIED"


def test_aggregate_worm_receipt_cannot_replace_per_original_integrity_lock():
    external = [
        _attestation("WORM_LOCK", "storage", validation=False),
        _attestation("QUALIFIED_TIMESTAMP", "tsa"),
    ]
    strength = evaluate_proof_strength(_manifest(external, original_integrity_sealed=False))
    assert strength["gates"]["original_bytes_preserved"] is True
    assert strength["gates"]["every_original_individually_integrity_sealed"] is False
    assert strength["gates"]["worm_or_equivalent_immutability"] is False
    assert strength["level"] == "INTERNAL_INTEGRITY_VERIFIED"


def test_qualified_receipt_without_validation_material_cannot_raise_qualified_level():
    external = [
        _attestation("WORM_LOCK", "storage", validation=False),
        _attestation("QUALIFIED_TIMESTAMP", "tsa", validation=False),
        _attestation("QUALIFIED_SEAL", "seal", validation=False),
    ]
    strength = evaluate_proof_strength(_manifest(external))
    assert strength["gates"]["qualified_independent_timestamp"] is False
    assert strength["level"] == "ORIGINAL_IMMUTABILITY_VERIFIED"


def test_global_escrow_receipt_cannot_replace_per_original_custody_and_readback():
    external = [
        _attestation("QUALIFIED_TIMESTAMP", "qualified-a"),
        _attestation("QUALIFIED_SEAL", "qualified-a"),
        _attestation("PUBLIC_ANCHOR", "anchor-b", validation=False),
        _attestation("EVIDENCE_ESCROW", "escrow-c", validation=False),
    ]
    strength = evaluate_proof_strength(_manifest(external))
    assert strength["provider_independence"]["escrow_independent_from_qualified_and_anchor"] is True
    assert strength["gates"]["every_original_individually_escrowed"] is False
    assert strength["gates"]["independent_evidence_escrow"] is False
    assert strength["level"] == "MULTI_WITNESS_VERIFIED"


def test_independent_anchor_and_verified_per_original_escrow_require_distinct_witnesses_for_top_level():
    external = [
        _attestation("WORM_LOCK", "storage", validation=False),
        _attestation("QUALIFIED_TIMESTAMP", "qualified-a"),
        _attestation("QUALIFIED_SEAL", "qualified-a"),
        _attestation("PUBLIC_ANCHOR", "anchor-b", validation=False),
        _attestation(
            "EVIDENCE_ESCROW",
            "escrow-c",
            validation=False,
            evidence_id="ev-1",
            verified_original_escrow=True,
        ),
    ]
    strength = evaluate_proof_strength(_manifest(external))
    assert strength["provider_independence"]["provider_quorum_at_least_three"] is True
    assert strength["provider_independence"]["public_anchor_independent_from_qualified_provider"] is True
    assert strength["provider_independence"]["escrow_independent_from_qualified_and_anchor"] is True
    assert strength["gates"]["every_original_individually_escrowed"] is True
    assert strength["level"] == "MAXIMUM_INFRASTRUCTURE_VERIFIED"
