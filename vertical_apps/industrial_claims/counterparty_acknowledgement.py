from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping

from vertical_apps.industrial_claims.proof import ExternalAttestation, canonical_json_bytes, sha256_hex, sha512_hex


_ALLOWED_FACT_TYPES = {
    "REQUEST_REFERENCE",
    "REQUEST_RECEIVED_AT",
    "CHANGE_INSTRUCTION",
    "REVISION_TRANSITION",
    "DOCUMENT_RECEIPT",
    "DELIVERY_EVENT",
}
_ALLOWED_DECISIONS = {"CONFIRMED", "DISPUTED", "UNABLE_TO_CONFIRM"}


class CounterpartyAcknowledgementError(RuntimeError):
    pass


SignatureVerifier = Callable[[bytes, str, str], bool]


def _required(value: object, *, label: str, max_chars: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > max_chars or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise CounterpartyAcknowledgementError(f"invalid acknowledgement {label}")
    return text


def _aware_timestamp(value: object) -> str:
    text = _required(value, label="signed_at", max_chars=128)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CounterpartyAcknowledgementError("invalid acknowledgement signed_at") from exc
    if parsed.tzinfo is None:
        raise CounterpartyAcknowledgementError("acknowledgement signed_at must include timezone")
    return parsed.isoformat()


def _sha256(value: object, *, label: str) -> str:
    digest = _required(value, label=label, max_chars=64).lower()
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise CounterpartyAcknowledgementError(f"invalid acknowledgement {label}")
    return digest


def build_fact_acknowledgement_request(
    *,
    tenant_id: str,
    finding_id: str,
    evidence_id: str,
    evidence_sha256: str,
    fact_id: str,
    fact_type: str,
    fact_value: str,
) -> dict[str, Any]:
    normalized_type = _required(fact_type, label="fact_type", max_chars=64).upper()
    if normalized_type not in _ALLOWED_FACT_TYPES:
        raise CounterpartyAcknowledgementError("unsupported acknowledgement fact_type")
    body = {
        "schema": "CAUSLEDGER_COUNTERPARTY_FACT_ACK_V1",
        "tenant_id": _required(tenant_id, label="tenant_id", max_chars=128),
        "finding_id": _required(finding_id, label="finding_id"),
        "evidence_id": _required(evidence_id, label="evidence_id"),
        "evidence_sha256": _sha256(evidence_sha256, label="evidence_sha256"),
        "fact_id": _required(fact_id, label="fact_id"),
        "fact_type": normalized_type,
        "fact_value": _required(fact_value, label="fact_value", max_chars=8192),
        "scope": "FACT_CONFIRMATION_ONLY",
        "legal_effect_boundary": {
            "does_not_admit_liability": True,
            "does_not_admit_debt": True,
            "does_not_accept_recovery_amount": True,
            "does_not_waive_rights_or_defences": True,
            "does_not_amend_contract": True,
        },
        "allowed_decisions": sorted(_ALLOWED_DECISIONS),
    }
    return {
        **body,
        "request_sha256": sha256_hex(body),
        "request_sha512": sha512_hex(body),
    }


def verify_counterparty_fact_acknowledgement(
    *,
    request_payload: Mapping[str, Any],
    receipt: Mapping[str, Any],
    signature_verifier: SignatureVerifier,
) -> ExternalAttestation:
    request_body = {key: value for key, value in dict(request_payload).items() if key not in {"request_sha256", "request_sha512"}}
    expected_request_sha256 = sha256_hex(request_body)
    expected_request_sha512 = sha512_hex(request_body)
    if str(request_payload.get("request_sha256") or "").lower() != expected_request_sha256:
        raise CounterpartyAcknowledgementError("acknowledgement request SHA-256 mismatch")
    if str(request_payload.get("request_sha512") or "").lower() != expected_request_sha512:
        raise CounterpartyAcknowledgementError("acknowledgement request SHA-512 mismatch")
    if request_body.get("scope") != "FACT_CONFIRMATION_ONLY":
        raise CounterpartyAcknowledgementError("acknowledgement scope is not fact-only")
    boundary = request_body.get("legal_effect_boundary") or {}
    if not isinstance(boundary, Mapping) or not all(boundary.get(key) is True for key in (
        "does_not_admit_liability",
        "does_not_admit_debt",
        "does_not_accept_recovery_amount",
        "does_not_waive_rights_or_defences",
        "does_not_amend_contract",
    )):
        raise CounterpartyAcknowledgementError("acknowledgement legal-effect boundary is incomplete")

    counterparty_ref = _required(receipt.get("counterparty_ref"), label="counterparty_ref", max_chars=512)
    signer_ref = _required(receipt.get("signer_ref"), label="signer_ref", max_chars=512)
    decision = _required(receipt.get("decision"), label="decision", max_chars=64).upper()
    if decision not in _ALLOWED_DECISIONS:
        raise CounterpartyAcknowledgementError("unsupported acknowledgement decision")
    if _sha256(receipt.get("request_sha256"), label="request_sha256") != expected_request_sha256:
        raise CounterpartyAcknowledgementError("acknowledgement receipt is bound to another request")
    signed_at = _aware_timestamp(receipt.get("signed_at"))
    validation_ref = _required(receipt.get("validation_ref"), label="validation_ref")
    signature = _required(receipt.get("signature"), label="signature", max_chars=32768)
    signature_algorithm = _required(receipt.get("signature_algorithm"), label="signature_algorithm", max_chars=128)

    signed_body = {
        "schema": "CAUSLEDGER_COUNTERPARTY_FACT_ACK_RECEIPT_V1",
        "request_sha256": expected_request_sha256,
        "counterparty_ref": counterparty_ref,
        "signer_ref": signer_ref,
        "decision": decision,
        "signed_at": signed_at,
        "validation_ref": validation_ref,
        "signature_algorithm": signature_algorithm,
    }
    if signature_verifier(canonical_json_bytes(signed_body), signature, signer_ref) is not True:
        raise CounterpartyAcknowledgementError("counterparty acknowledgement signature is invalid")

    evidence_id = _required(request_body.get("evidence_id"), label="evidence_id")
    evidence_sha256 = _sha256(request_body.get("evidence_sha256"), label="evidence_sha256")
    provider_ref = sha256_hex({"signed_body": signed_body, "signature": signature})
    verified = decision == "CONFIRMED"
    return ExternalAttestation(
        kind="COUNTERPARTY_ACKNOWLEDGEMENT",
        provider=f"COUNTERPARTY:{counterparty_ref}",
        state="VERIFIED" if verified else decision,
        digest_algorithm="SHA-256",
        digest=evidence_sha256,
        provider_ref=provider_ref if verified else None,
        issued_at=signed_at,
        validation_ref=validation_ref,
        details={
            "tenant_id": request_body.get("tenant_id"),
            "subject_ref": request_body.get("finding_id"),
            "purpose": "LIMITED_FACT_ACKNOWLEDGEMENT",
            "evidence_id": evidence_id,
            "fact_id": request_body.get("fact_id"),
            "fact_type": request_body.get("fact_type"),
            "fact_value": request_body.get("fact_value"),
            "decision": decision,
            "request_sha256": expected_request_sha256,
            "request_sha512": expected_request_sha512,
            "signature_cryptographically_verified": True,
            "fact_confirmation_only": True,
            "does_not_admit_liability": True,
            "does_not_admit_debt": True,
            "does_not_accept_recovery_amount": True,
            "does_not_waive_rights_or_defences": True,
            "does_not_amend_contract": True,
            "acknowledgement_does_not_itself_establish_legal_recoverability": True,
        },
    )
