from __future__ import annotations

import json
import sqlite3

import pytest

from vertical_apps.industrial_claims.proof import ExternalAttestation
from vertical_apps.industrial_claims.proof_attestation_archive import (
    EXPECTED_PURPOSE,
    ProofAttestationArchive,
    ProofAttestationArchiveError,
)


def _receipt(kind: str, target: str, *, subject: str | None = None):
    subject_ref = subject or f"causledger:proof-target:{target}"
    return ExternalAttestation(
        kind=kind,
        provider=f"provider-{kind.lower()}",
        state="UNAVAILABLE",
        digest_algorithm="SHA-256",
        digest=target,
        details={
            "subject_ref": subject_ref,
            "purpose": EXPECTED_PURPOSE,
            "fail_closed": True,
        },
    ).as_dict()


def _receipts(target: str):
    return [
        _receipt("QUALIFIED_TIMESTAMP", target),
        _receipt("QUALIFIED_SEAL", target),
        _receipt("QUALIFIED_SIGNATURE", target),
        _receipt("PUBLIC_ANCHOR", target),
    ]


def test_archive_preserves_and_recovers_receipts_with_verified_hash_chain(tmp_path):
    database = tmp_path / "archive.sqlite3"
    archive = ProofAttestationArchive(database)
    target = "a" * 64
    stored = archive.archive_operation(
        operation_id="proofext-op-1",
        tenant_id="tenant-a",
        target_sha256=target,
        receipts=_receipts(target),
    )
    assert stored["receipt_count"] == 4
    assert stored["subject_ref"] == f"causledger:proof-target:{target}"
    assert stored["archive_chain_head_sha256"]

    recovered = archive.operation_receipts(tenant_id="tenant-a", operation_id="proofext-op-1")
    assert recovered["archive_chain_verified"] is True
    assert recovered["receipt_count"] == 4
    assert recovered["receipts_sha256"] == stored["receipts_sha256"]
    assert [item["kind"] for item in recovered["receipts"]] == [
        "QUALIFIED_TIMESTAMP",
        "QUALIFIED_SEAL",
        "QUALIFIED_SIGNATURE",
        "PUBLIC_ANCHOR",
    ]


def test_archive_rejects_receipt_bound_to_another_target_or_subject(tmp_path):
    archive = ProofAttestationArchive(tmp_path / "binding.sqlite3")
    target = "b" * 64
    wrong_digest = _receipts(target)
    wrong_digest[0]["digest"] = "c" * 64
    with pytest.raises(ProofAttestationArchiveError, match="another proof target"):
        archive.archive_operation(
            operation_id="proofext-op-digest",
            tenant_id="tenant-a",
            target_sha256=target,
            receipts=wrong_digest,
        )

    wrong_subject = _receipts(target)
    wrong_subject[0]["details"]["subject_ref"] = "causledger:proof-target:" + "d" * 64
    with pytest.raises(ProofAttestationArchiveError, match="subject binding"):
        archive.archive_operation(
            operation_id="proofext-op-subject",
            tenant_id="tenant-a",
            target_sha256=target,
            receipts=wrong_subject,
        )


def test_archive_rejects_duplicate_operation_and_detects_direct_database_tampering(tmp_path):
    database = tmp_path / "tamper.sqlite3"
    archive = ProofAttestationArchive(database)
    target = "e" * 64
    receipts = _receipts(target)
    archive.archive_operation(
        operation_id="proofext-op-tamper",
        tenant_id="tenant-a",
        target_sha256=target,
        receipts=receipts,
    )
    with pytest.raises(ProofAttestationArchiveError, match="already archived"):
        archive.archive_operation(
            operation_id="proofext-op-tamper",
            tenant_id="tenant-a",
            target_sha256=target,
            receipts=receipts,
        )

    with sqlite3.connect(database) as conn:
        conn.execute("DROP TRIGGER causledger_external_attestation_no_update")
        row = conn.execute(
            "SELECT sequence,payload_json FROM causledger_external_attestation_receipts ORDER BY sequence LIMIT 1"
        ).fetchone()
        payload = json.loads(row[1])
        payload["details"]["fail_closed"] = False
        conn.execute(
            "UPDATE causledger_external_attestation_receipts SET payload_json=? WHERE sequence=?",
            (json.dumps(payload, sort_keys=True, separators=(",", ":")), row[0]),
        )
        conn.commit()

    with pytest.raises(ProofAttestationArchiveError, match="payload hash mismatch"):
        archive.operation_receipts(tenant_id="tenant-a", operation_id="proofext-op-tamper")
