from vertical_apps.industrial_claims.proof_readiness import evaluate_proof_strength


def _manifest(*, raw_content_persisted: bool, integrity_sealed: bool, immutability_verified: bool):
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
                    "original_immutability_verified": immutability_verified,
                    "source_authenticated": True,
                },
            }
        ],
        "external_attestations": [],
    }


def test_verified_immutability_cannot_upgrade_missing_original_bytes():
    result = evaluate_proof_strength(
        _manifest(raw_content_persisted=False, integrity_sealed=True, immutability_verified=True)
    )
    assert result["gates"]["every_original_individually_integrity_sealed"] is True
    assert result["gates"]["every_original_immutability_verified"] is True
    assert result["gates"]["original_bytes_preserved"] is False
    assert result["gates"]["worm_or_equivalent_immutability"] is False
    assert result["level"] == "INTERNAL_INTEGRITY_VERIFIED"


def test_internal_integrity_seal_alone_never_establishes_original_immutability():
    result = evaluate_proof_strength(
        _manifest(raw_content_persisted=True, integrity_sealed=True, immutability_verified=False)
    )
    assert result["gates"]["original_bytes_preserved"] is True
    assert result["gates"]["every_original_individually_integrity_sealed"] is True
    assert result["gates"]["every_original_immutability_verified"] is False
    assert result["gates"]["worm_or_equivalent_immutability"] is False
    assert result["level"] == "INTERNAL_INTEGRITY_VERIFIED"


def test_original_immutability_requires_retained_bytes_integrity_and_verified_immutability():
    no_integrity = evaluate_proof_strength(
        _manifest(raw_content_persisted=True, integrity_sealed=False, immutability_verified=True)
    )
    assert no_integrity["gates"]["every_original_individually_integrity_sealed"] is False
    assert no_integrity["level"] == "INTERNAL_INTEGRITY_VERIFIED"

    complete = evaluate_proof_strength(
        _manifest(raw_content_persisted=True, integrity_sealed=True, immutability_verified=True)
    )
    assert complete["gates"]["worm_or_equivalent_immutability"] is True
    assert complete["level"] == "ORIGINAL_IMMUTABILITY_VERIFIED"
