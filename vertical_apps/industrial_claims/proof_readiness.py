from __future__ import annotations

from typing import Any, Mapping

from vertical_apps.industrial_claims.proof_trust_policy import evaluate_provider_independence


_LEVELS = (
    "UNVERIFIED",
    "INTERNAL_INTEGRITY_VERIFIED",
    "ORIGINAL_IMMUTABILITY_VERIFIED",
    "INDEPENDENT_TIME_VERIFIED",
    "QUALIFIED_ORIGIN_VERIFIED",
    "MULTI_WITNESS_VERIFIED",
    "MAXIMUM_INFRASTRUCTURE_VERIFIED",
)


def _strict_true(value: object) -> bool:
    return value is True


def _original_has_verified_escrow(item: Mapping[str, Any]) -> bool:
    evidence_id = str(item.get("evidence_id") or "").strip()
    evidence_sha256 = str((item.get("hashes") or {}).get("sha256") or "").strip().lower()
    if not evidence_id or len(evidence_sha256) != 64:
        return False
    external = [entry for entry in list(item.get("external_attestations") or []) if isinstance(entry, Mapping)]
    for receipt in external:
        details = receipt.get("details") or {}
        if not isinstance(details, Mapping):
            continue
        if str(receipt.get("kind") or "") != "EVIDENCE_ESCROW":
            continue
        if str(receipt.get("state") or "").upper() not in {"VALID", "VERIFIED"}:
            continue
        if not str(receipt.get("provider_ref") or "").strip():
            continue
        if str(receipt.get("digest_algorithm") or "").upper() != "SHA-256":
            continue
        if str(receipt.get("digest") or "").strip().lower() != evidence_sha256:
            continue
        if str(details.get("evidence_id") or "").strip() != evidence_id:
            continue
        # These flags are set only by the dedicated escrow adapter after it has
        # verified request/receipt binding and read back the same deposited bytes.
        if not _strict_true(details.get("binding_verified")):
            continue
        if not _strict_true(details.get("original_bytes_escrowed")):
            continue
        if not _strict_true(details.get("read_back_verified")):
            continue
        return True
    return False


def evaluate_proof_strength(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Describe proof strength without assigning a misleading numeric confidence score.

    Aggregate sealing or escrow cannot substitute for preservation of every original.
    Original-level gates therefore require retained bytes plus per-evidence verified
    immutability/escrow evidence; a global provider receipt can never manufacture the
    maximum infrastructure level.
    """
    evidence = list(manifest.get("evidence") or [])
    external = list(manifest.get("external_attestations") or [])
    verified = [item for item in external if str(item.get("state") or "").upper() in {"VALID", "VERIFIED"}]
    kinds = {str(item.get("kind") or "") for item in verified}
    providers = {str(item.get("provider") or "").strip() for item in verified if str(item.get("provider") or "").strip()}
    independence = evaluate_provider_independence(manifest)

    internal_integrity = bool((manifest.get("manifest_hashes") or {}).get("sha256")) and bool(
        (manifest.get("attestation_target") or {}).get("sha256")
    ) and bool((manifest.get("dual_hash_coverage") or {}).get("sha256"))
    originals = bool(evidence) and all(bool(item.get("raw_content_persisted")) for item in evidence)
    every_original_integrity_sealed = bool(evidence) and all(
        bool((item.get("assurance_dimensions") or {}).get("integrity_sealed"))
        for item in evidence
    )
    every_original_immutability_verified = bool(evidence) and all(
        str(item.get("immutability") or "").strip().upper() in {"WORM_LOCKED", "IMMUTABLE_VERIFIED"}
        for item in evidence
    )
    immutability = originals and every_original_integrity_sealed and every_original_immutability_verified
    independent_time = immutability and "QUALIFIED_TIMESTAMP" in kinds and independence["qualified_timestamp_complete"]
    qualified_origin = independent_time and bool({"QUALIFIED_SEAL", "QUALIFIED_SIGNATURE"} & kinds) and independence["qualified_origin_complete"]
    multi_witness = (
        qualified_origin
        and "PUBLIC_ANCHOR" in kinds
        and len(providers) >= 2
        and independence["public_anchor_independent_from_qualified_provider"]
    )
    source_authenticated = bool(evidence) and all(
        bool((item.get("assurance_dimensions") or {}).get("source_authenticated")) for item in evidence
    )
    dual_hash = bool((manifest.get("dual_hash_coverage") or {}).get("sha512"))
    every_original_escrowed = bool(evidence) and all(
        isinstance(item, Mapping) and _original_has_verified_escrow(item)
        for item in evidence
    )
    escrow = "EVIDENCE_ESCROW" in kinds and every_original_escrowed
    maximum = (
        multi_witness
        and source_authenticated
        and dual_hash
        and escrow
        and independence["escrow_independent_from_qualified_and_anchor"]
        and independence["provider_quorum_at_least_three"]
    )

    gates = {
        "internal_integrity": internal_integrity,
        "original_bytes_preserved": originals,
        "every_original_individually_integrity_sealed": every_original_integrity_sealed,
        "every_original_immutability_verified": every_original_immutability_verified,
        "worm_or_equivalent_immutability": immutability,
        "qualified_independent_timestamp": independent_time,
        "qualified_seal_or_signature": qualified_origin,
        "independent_public_anchor": "PUBLIC_ANCHOR" in kinds,
        "public_anchor_independent_from_qualified_provider": independence["public_anchor_independent_from_qualified_provider"],
        "independent_provider_quorum_at_least_two": len(providers) >= 2,
        "maximum_provider_quorum_at_least_three": independence["provider_quorum_at_least_three"],
        "source_authentication_for_all_evidence": source_authenticated,
        "dual_sha256_sha512_coverage": dual_hash,
        "every_original_individually_escrowed": every_original_escrowed,
        "independent_evidence_escrow": escrow,
        "escrow_independent_from_qualified_and_anchor": independence["escrow_independent_from_qualified_and_anchor"],
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
        "provider_independence": independence,
        "missing_for_maximum_infrastructure": missing_for_maximum,
        "counterparty_acknowledgement_is_additional_not_always_obtainable": True,
        "proof_strength_does_not_establish_factual_truth_or_legal_recoverability": True,
    }
