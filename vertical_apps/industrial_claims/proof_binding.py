from __future__ import annotations

from typing import Any, Sequence

from vertical_apps.industrial_claims.proof import ExternalAttestation


class EvidenceAttestationBindingError(RuntimeError):
    pass


def _expected_digest(evidence: Any, algorithm: str) -> str | None:
    if algorithm == "SHA-256":
        return str(getattr(evidence, "content_hash", "") or "").strip().lower() or None
    if algorithm == "SHA-512":
        metadata = dict(getattr(evidence, "metadata", {}) or {})
        return str(metadata.get("content_sha512") or "").strip().lower() or None
    return None


def validate_evidence_attestation_bindings(
    evidence: Sequence[Any],
    attestations: Sequence[ExternalAttestation],
) -> None:
    """Reject verified evidence attestations that are ambiguous or mis-bound.

    A provider receipt that names an evidence_id is useful only if the verified
    digest is exactly the digest of that evidence. A verified receipt naming an
    unknown evidence item, an unavailable digest algorithm, or a different digest
    is a hard error rather than a weaker assurance state.
    """
    by_id: dict[str, Any] = {}
    for item in evidence:
        evidence_id = str(getattr(item, "evidence_id", "") or "").strip()
        if not evidence_id:
            raise EvidenceAttestationBindingError("evidence attestation binding requires evidence identity")
        if evidence_id in by_id:
            raise EvidenceAttestationBindingError("duplicate evidence identity makes attestation binding ambiguous")
        by_id[evidence_id] = item

    for attestation in attestations:
        evidence_id = str(attestation.details.get("evidence_id") or "").strip()
        if not evidence_id or not attestation.verified:
            continue
        item = by_id.get(evidence_id)
        if item is None:
            raise EvidenceAttestationBindingError("verified attestation references unknown evidence")
        algorithm = attestation.digest_algorithm.upper()
        expected = _expected_digest(item, algorithm)
        if expected is None:
            raise EvidenceAttestationBindingError("verified attestation requires the corresponding evidence digest")
        if str(attestation.digest).strip().lower() != expected:
            raise EvidenceAttestationBindingError("verified attestation digest does not match referenced evidence")
