from __future__ import annotations

from email import policy
from email.parser import BytesParser
from typing import Any

from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.secure_capture import SourceAuthenticationReceipt


def extract_email_forensic_metadata(
    raw_eml: bytes,
    *,
    authentication: SourceAuthenticationReceipt | None = None,
) -> dict[str, Any]:
    """Extract deterministic email provenance while keeping validation truth separate.

    Merely observing DKIM-Signature or Authentication-Results headers never marks
    DKIM as cryptographically valid. A verified external/source receipt is needed
    for that upgrade.
    """
    if not isinstance(raw_eml, bytes) or not raw_eml:
        raise ValueError("raw RFC822 bytes are required")
    message = BytesParser(policy=policy.default).parsebytes(raw_eml)
    raw_hashes = dual_digest(raw_eml)
    attachments: list[dict[str, Any]] = []
    for index, part in enumerate(message.iter_attachments()):
        payload = part.get_payload(decode=True) or b""
        hashes = dual_digest(payload)
        attachments.append({
            "index": index,
            "filename": part.get_filename(),
            "content_type": part.get_content_type(),
            "content_disposition": part.get_content_disposition(),
            "content_id": part.get("Content-ID"),
            "sha256": hashes["sha256"],
            "sha512": hashes["sha512"],
            "byte_length": hashes["byte_length"],
        })

    dkim_headers = message.get_all("DKIM-Signature", [])
    auth_results = message.get_all("Authentication-Results", [])
    received_headers = message.get_all("Received", [])
    source_state = "UNVERIFIED"
    source_provider_ref = None
    source_checked_at = None
    if authentication is not None:
        source_state = authentication.state.strip().upper()
        source_provider_ref = authentication.provider_ref
        source_checked_at = authentication.checked_at
    elif dkim_headers:
        source_state = "DKIM_PRESENT_UNVERIFIED"

    return {
        "format": "RFC822_EML",
        "raw_eml_sha256": raw_hashes["sha256"],
        "raw_eml_sha512": raw_hashes["sha512"],
        "raw_eml_byte_length": raw_hashes["byte_length"],
        "message_id": message.get("Message-ID"),
        "date_header": message.get("Date"),
        "from_header": message.get("From"),
        "to_header": message.get("To"),
        "cc_header": message.get("Cc"),
        "reply_to_header": message.get("Reply-To"),
        "subject_header": message.get("Subject"),
        "in_reply_to": message.get("In-Reply-To"),
        "references": message.get("References"),
        "received_header_count": len(received_headers),
        "received_headers": list(received_headers),
        "dkim_signature_present": bool(dkim_headers),
        "dkim_signature_headers": list(dkim_headers),
        "authentication_results_headers": list(auth_results),
        "source_authentication_state": source_state,
        "source_authentication_provider_ref": source_provider_ref,
        "source_authentication_checked_at": source_checked_at,
        "header_presence_is_not_cryptographic_validation": True,
        "attachments": attachments,
        "attachment_count": len(attachments),
    }
