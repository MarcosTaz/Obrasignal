from __future__ import annotations

from typing import Any, Mapping


_LEVELS = (
    "UNVERIFIED",
    "INTERNAL_INTEGRITY_VERIFIED",
    "ORIGINAL_IMMUTABILITY_VERIFIED",
    "INDEPENDENT_TIME_VERIFIED",
    "QUALIFIED_ORIGIN_VERIFIED",
    "MULTI_WITNESS_VERIFIED",
    "MAXIMUM_INFRASTRUCTURE_VERIFIED",
)


def evaluate_proof_strength(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Describe proof strength without assigning a misleading numeric confidence score."""
    evidence = list(manifest.get("evidence") or [])
    external = list(manifest.get("external_attestations") or [])
    verified = [item for item in external if str(item.get("state") or "").upper() in {"VALID", "VERIFIED"}]
    kinds = {str(item.get("kind") or "") for item in verified}
    providers = {str(item.get("provider") or "").strip() for item in verified if str(item.get("provider") or "").strip()}

    internal_integrity = bool((manifest.get("manifest_hashes") or {}).get("sha256")) and bool(
        (manifest.get("attestation_target") or {}).get("sha256")
    ) and bool((manifest.get("dual_hash_coverage") or {}).get("sha256"))
    originals = bool(evidence) and all(bool(item.get("raw_content_persisted")) for item in evidence)
    immutability = originals and "WORM_LOCK" in kinds
    independent_time = immutability and "QUALIFIED_TIMESTAMP" in kinds
    qualified_origin = independent_time and bool({"QUALIFIED_SEAL", "QUALIFIED_SIGNATURE"} & kinds)
    multi_witness = qualified_origin and "PUBLIC_ANCHOR" in kinds and len(providers) >= 2
    source_authenticated = bool(evidence) and all(
        bool((item.get("assurance_dimensions") or {}).get("source_authenticated")) for item in evidence
    )
    dual_hash = bool((manifest.get("dual_hash_coverage") or {}).get("sha512"))
    escrow = "EVIDENCE_ESCROW" in kinds
    maximum = multi_witness and source_authenticated and dual_hash and escrow

    gates = {
        "internal_integrity": internal_integrity,
        "original_bytes_preserved": originals,
        "worm_or_equivalent_immutability": immutability,
        "qualified_independent_timestamp": independent_time,
        "qualified_seal_or_signature": qualified_origin,
        "independent_public_anchor": "PUBLIC_ANCHOR" in kinds,
        "independent_provider_quorum_at_least_two": len(providers) >= 2,
        "source_authentication_for_all_evidence": source_authenticated,
        "dual_sha256_sha512_coverage": dual_hash,
        "independent_evidence_escrow": escrow,
        "counterparty_acknowledgement": "COUNTERPARTY_ACKNOWLEDGEMENT" in kinds,
    }
    if maximum:
        level = "MAXIMUM_INFRASTRUCTURE_VERIFIED"
    elif multi_witness:
        level = "MULTI_WITNESS_VERIFIED"
    elif qualified_origin:
        level = "QUALIFIED_ORIGIN_VERIFIED"
    elif independent_time:
        level = "INDEPENDENT_TIME_VERIFIED"
    elif immutability:
        level = "ORIGINAL_IMMUTABILITY_VERIFIED"
    elif internal_integrity:
        level = "INTERNAL_INTEGRITY_VERIFIED"
    else:
        level = "UNVERIFIED"

    missing_for_maximum = [name for name, satisfied in gates.items() if not satisfied and name != "counterparty_acknowledgement"]
    return {
        "level": level,
        "level_order": list(_LEVELS),
        "gates": gates,
        "missing_for_maximum_infrastructure": missing_for_maximum,
        "counterparty_acknowledgement_is_additional_not_always_obtainable": True,
        "proof_strength_does_not_establish_factual_truth_or_legal_recoverability": True,
    }
