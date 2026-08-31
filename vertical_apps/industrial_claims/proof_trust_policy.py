from __future__ import annotations

from typing import Any, Mapping


_VERIFIED = {"VALID", "VERIFIED"}
_QUALIFIED = {"QUALIFIED_TIMESTAMP", "QUALIFIED_SEAL", "QUALIFIED_SIGNATURE"}


def _verified(item: Mapping[str, Any]) -> bool:
    return str(item.get("state") or "").upper() in _VERIFIED and bool(str(item.get("provider_ref") or "").strip())


def _complete(item: Mapping[str, Any]) -> bool:
    if not _verified(item):
        return False
    if str(item.get("kind") or "") not in _QUALIFIED:
        return True
    return bool(str(item.get("validation_ref") or "").strip()) and bool(str(item.get("issued_at") or "").strip())


def evaluate_provider_independence(manifest: Mapping[str, Any]) -> dict[str, Any]:
    external = [item for item in list(manifest.get("external_attestations") or []) if isinstance(item, Mapping)]
    verified = [item for item in external if _verified(item)]

    def providers(kind: str, *, complete: bool = False) -> set[str]:
        return {
            str(item.get("provider") or "").strip()
            for item in verified
            if str(item.get("kind") or "") == kind
            and (not complete or _complete(item))
            and str(item.get("provider") or "").strip()
        }

    timestamp = providers("QUALIFIED_TIMESTAMP", complete=True)
    seal = providers("QUALIFIED_SEAL", complete=True) | providers("QUALIFIED_SIGNATURE", complete=True)
    worm = providers("WORM_LOCK")
    anchor = providers("PUBLIC_ANCHOR")
    escrow = providers("EVIDENCE_ESCROW")
    all_providers = {
        str(item.get("provider") or "").strip()
        for item in verified
        if str(item.get("provider") or "").strip()
    }
    anchor_independent = bool(anchor - (timestamp | seal))
    escrow_independent = bool(escrow - (timestamp | seal | anchor))
    return {
        "qualified_timestamp_complete": bool(timestamp),
        "qualified_origin_complete": bool(seal),
        "worm_receipt_present": bool(worm),
        "public_anchor_present": bool(anchor),
        "escrow_receipt_present": bool(escrow),
        "public_anchor_independent_from_qualified_provider": anchor_independent,
        "escrow_independent_from_qualified_and_anchor": escrow_independent,
        "provider_quorum_at_least_two": len(all_providers) >= 2,
        "provider_quorum_at_least_three": len(all_providers) >= 3,
        "verified_provider_count": len(all_providers),
        "providers": {
            "timestamp": sorted(timestamp),
            "origin": sorted(seal),
            "worm": sorted(worm),
            "anchor": sorted(anchor),
            "escrow": sorted(escrow),
        },
        "single_provider_cannot_satisfy_independent_witness_policy": True,
    }
