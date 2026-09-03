from __future__ import annotations

from vertical_apps.industrial_claims.proof_readiness import evaluate_proof_strength


def test_hashes_alone_never_claim_maximum_proof_strength():
    manifest = {
        "manifest_hashes": {"sha256": "a" * 64},
        "attestation_target": {"sha256": "b" * 64},
        "dual_hash_coverage": {"sha256": True, "sha512": False},
        "evidence": [
            {
                "raw_content_persisted": False,
                "assurance_dimensions": {"source_authenticated": False},
            }
        ],
        "external_attestations": [],
    }
    strength = evaluate_proof_strength(manifest)
    assert strength["level"] == "INTERNAL_INTEGRITY_VERIFIED"
    assert strength["gates"]["qualified_independent_timestamp"] is False
    assert strength["gates"]["independent_evidence_escrow"] is False
    assert strength["proof_strength_does_not_establish_factual_truth_or_legal_recoverability"] is True
