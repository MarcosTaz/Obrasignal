"""Privacy-safe provenance helpers for customer-critical derivations.

This module records bounded derivation metadata only. It is not a business-value,
scoring, source, privacy-retention, or persistence-schema authority.
"""
from __future__ import annotations

import hashlib
import json


LINEAGE_CONTRACT_VERSION = "decision-lineage.v1"
PROFILE_FINGERPRINT_ALGORITHM = "sha256-canonical-json.v1"


def canonical_fingerprint(value) -> str:
    """Return a deterministic SHA-256 fingerprint without retaining raw input."""
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def decision_profile_lineage(profile: dict) -> dict:
    """Describe which exact normalized profile content fed one decision.

    Fingerprint-only lineage detects input drift but intentionally cannot recreate
    deleted/overwritten private profile content. Reconstruction therefore remains
    PARTIAL until a Privacy-approved historical-input contract exists.
    """
    if not isinstance(profile, dict):
        raise TypeError("profile_lineage_requires_mapping")
    return {
        "contract_version": LINEAGE_CONTRACT_VERSION,
        "fingerprint": canonical_fingerprint(profile),
        "fingerprint_algorithm": PROFILE_FINGERPRINT_ALGORITHM,
        "reconstruction": "FINGERPRINT_ONLY",
        "privacy_class": "HASHED_DERIVATION_METADATA",
    }
