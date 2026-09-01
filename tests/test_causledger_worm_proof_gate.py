from vertical_apps.industrial_claims.proof_readiness import evaluate_proof_strength


def _manifest(*, raw_content_persisted: bool, integrity_sealed: bool):
    return {
        "manifest_hashes": {"sha256": "a" * 64},
        "attestation_target": {"sha256": "b" * 64},
        "dual_hash_coverage": {"sha256": True, "sha512": True},
        "evidence": [
            {
                "evidence_id": "ev-1",
                "raw_content_persisted": raw_content_persisted,
                "assurance_dimensions": {
                    "integrity_sealed": integrity_sealed,
                    "source_authenticated": True,
                },
            }
        ],
        "external_attestations": [
            {
                "kind": "WORM_LOCK",
                "provider": "synthetic-worm",
                "state": "VERIFIED",
                "details": {"evidence_id": "ev-1"},
            }
        ],
    }


def test_verified_worm_receipt_cannot_upgrade_missing_original_bytes_to_immutability():
    result = evaluate_proof_strength(_manifest(raw_content_persisted=False, integrity_sealed=True))
    assert result["gates"]["every_original_individually_integrity_sealed"] is True
    assert result["gates"]["original_bytes_preserved"] is False
    assert result["gates"]["worm_or_equivalent_immutability"] is False
    assert result["level"] == "INTERNAL_INTEGRITY_VERIFIED"


def test_original_immutability_requires_both_retained_bytes_and_individual_integrity_seal():
    no_seal = evaluate_proof_strength(_manifest(raw_content_persisted=True, integrity_sealed=False))
    assert no_seal["gates"]["original_bytes_preserved"] is True
    assert no_seal["gates"]["every_original_individually_integrity_sealed"] is False
    assert no_seal["level"] == "INTERNAL_INTEGRITY_VERIFIED"

    complete = evaluate_proof_strength(_manifest(raw_content_persisted=True, integrity_sealed=True))
    assert complete["gates"]["worm_or_equivalent_immutability"] is True
    assert complete["level"] == "ORIGINAL_IMMUTABILITY_VERIFIED"
