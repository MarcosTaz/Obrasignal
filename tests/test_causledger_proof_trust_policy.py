from __future__ import annotations

from vertical_apps.industrial_claims.proof_readiness import evaluate_proof_strength
from vertical_apps.industrial_claims.proof_trust_policy import evaluate_provider_independence


def _attestation(kind: str, provider: str, *, validation: bool = True):
    return {
        "kind": kind,
        "provider": provider,
        "state": "VERIFIED",
        "provider_ref": f"{provider}:{kind}:1",
        "validation_ref": f"{provider}:validation:1" if validation else None,
        "issued_at": "2026-08-31T23:00:00+00:00" if validation else None,
    }


def _manifest(external):
    return {
        "manifest_hashes": {"sha256": "a" * 64},
        "attestation_target": {"sha256": "b" * 64},
        "dual_hash_coverage": {"sha256": True, "sha512": True},
        "evidence": [
            {
                "raw_content_persisted": True,
                "assurance_dimensions": {"source_authenticated": True},
            }
        ],
        "external_attestations": list(external),
    }


def test_one_provider_cannot_create_independent_witness_strength():
    external = [
        _attestation("WORM_LOCK", "provider-a", validation=False),
        _attestation("QUALIFIED_TIMESTAMP", "provider-a"),
        _attestation("QUALIFIED_SEAL", "provider-a"),
        _attestation("PUBLIC_ANCHOR", "provider-a", validation=False),
        _attestation("EVIDENCE_ESCROW", "provider-a", validation=False),
    ]
    independence = evaluate_provider_independence(_manifest(external))
    assert independence["public_anchor_independent_from_qualified_provider"] is False
    assert independence["provider_quorum_at_least_two"] is False
    assert evaluate_proof_strength(_manifest(external))["level"] == "QUALIFIED_ORIGIN_VERIFIED"


def test_qualified_receipt_without_validation_material_cannot_raise_qualified_level():
    external = [
        _attestation("WORM_LOCK", "storage", validation=False),
        _attestation("QUALIFIED_TIMESTAMP", "tsa", validation=False),
        _attestation("QUALIFIED_SEAL", "seal", validation=False),
    ]
    strength = evaluate_proof_strength(_manifest(external))
    assert strength["gates"]["qualified_independent_timestamp"] is False
    assert strength["level"] == "ORIGINAL_IMMUTABILITY_VERIFIED"


def test_independent_anchor_and_escrow_require_distinct_witnesses_for_top_level():
    external = [
        _attestation("WORM_LOCK", "storage", validation=False),
        _attestation("QUALIFIED_TIMESTAMP", "qualified-a"),
        _attestation("QUALIFIED_SEAL", "qualified-a"),
        _attestation("PUBLIC_ANCHOR", "anchor-b", validation=False),
        _attestation("EVIDENCE_ESCROW", "escrow-c", validation=False),
    ]
    strength = evaluate_proof_strength(_manifest(external))
    assert strength["provider_independence"]["provider_quorum_at_least_three"] is True
    assert strength["provider_independence"]["public_anchor_independent_from_qualified_provider"] is True
    assert strength["provider_independence"]["escrow_independent_from_qualified_and_anchor"] is True
    assert strength["level"] == "MAXIMUM_INFRASTRUCTURE_VERIFIED"
