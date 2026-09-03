from __future__ import annotations

from vertical_apps.industrial_claims.email_forensics import extract_email_forensic_metadata
from vertical_apps.industrial_claims.secure_capture import SourceAuthenticationReceipt


def test_email_forensics_preserves_headers_and_attachment_hashes_without_fake_dkim_validation():
    raw = (
        b"From: customer@example.com\r\n"
        b"To: supplier@example.com\r\n"
        b"Message-ID: <change-17@example.com>\r\n"
        b"Date: Mon, 31 Aug 2026 20:00:00 +0000\r\n"
        b"Subject: Drawing R17\r\n"
        b"DKIM-Signature: v=1; a=rsa-sha256; d=example.com; s=test; b=fake\r\n"
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: multipart/mixed; boundary=abc\r\n\r\n"
        b"--abc\r\nContent-Type: text/plain\r\n\r\nPlease use R17\r\n"
        b"--abc\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment; filename=R17.pdf\r\n"
        b"Content-Transfer-Encoding: base64\r\n\r\nUEZERGF0YQ==\r\n--abc--\r\n"
    )
    metadata = extract_email_forensic_metadata(raw)
    assert metadata["message_id"] == "<change-17@example.com>"
    assert metadata["dkim_signature_present"] is True
    assert metadata["source_authentication_state"] == "DKIM_PRESENT_UNVERIFIED"
    assert metadata["header_presence_is_not_cryptographic_validation"] is True
    assert metadata["attachment_count"] == 1
    assert metadata["attachments"][0]["filename"] == "R17.pdf"
    assert len(metadata["attachments"][0]["sha256"]) == 64


def test_email_forensics_accepts_verified_external_authentication_receipt():
    receipt = SourceAuthenticationReceipt(
        state="DKIM_VALID",
        scheme="DKIM",
        provider="mail-verifier",
        provider_ref="dkim:receipt:1",
        checked_at="2026-08-31T20:01:00+00:00",
    )
    metadata = extract_email_forensic_metadata(
        b"From: customer@example.com\r\nMessage-ID: <m@example.com>\r\n\r\nBody",
        authentication=receipt,
    )
    assert metadata["source_authentication_state"] == "DKIM_VALID"
    assert metadata["source_authentication_provider_ref"] == "dkim:receipt:1"
