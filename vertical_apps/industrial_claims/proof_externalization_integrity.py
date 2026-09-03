from __future__ import annotations

import sqlite3
from typing import Any

from vertical_apps.industrial_claims.proof_attestation_archive import (
    ProofAttestationArchive,
    ProofAttestationArchiveError,
)
from vertical_apps.industrial_claims.proof_externalization_audit import (
    ProofExternalizationAuditError,
    ProofExternalizationAuditStore,
)


class ProofExternalizationIntegrityError(RuntimeError):
    pass


def _required(value: object, *, label: str, maximum: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise ProofExternalizationIntegrityError(f"invalid {label}")
    return text


def _operation_archive_head(
    archive: ProofAttestationArchive,
    *,
    tenant_id: str,
    operation_id: str,
) -> tuple[str | None, int]:
    with sqlite3.connect(archive.path) as conn:
        conn.row_factory = sqlite3.Row
        rows = list(
            conn.execute(
                """SELECT receipt_hash FROM causledger_external_attestation_receipts
                   WHERE tenant_id=? AND operation_id=? ORDER BY sequence""",
                (tenant_id, operation_id),
            ).fetchall()
        )
    if not rows:
        return None, 0
    return str(rows[-1]["receipt_hash"]), len(rows)


def verify_externalization_operation_integrity(
    *,
    audit_store: ProofExternalizationAuditStore,
    attestation_archive: ProofAttestationArchive,
    tenant_id: str,
    finding_id: str,
    operation_id: str,
) -> dict[str, Any]:
    """Cross-verify one externalization operation across both durable ledgers.

    Audit integrity and receipt-archive integrity are necessary but not sufficient
    independently. This verifier proves that the terminal audit event references
    the exact archived receipt set and the exact archive head frozen when that
    operation was persisted. Later operations over the same target may advance the
    subject chain without invalidating the historical operation head.
    """
    tenant = _required(tenant_id, label="tenant_id", maximum=64)
    finding = _required(finding_id, label="finding_id")
    operation = _required(operation_id, label="operation_id", maximum=256)

    try:
        audit = audit_store.status(tenant_id=tenant, finding_id=finding)
    except ProofExternalizationAuditError as exc:
        raise ProofExternalizationIntegrityError("externalization audit chain is invalid") from exc
    events = (audit.get("operations") or {}).get(operation)
    if not isinstance(events, list) or not events:
        raise ProofExternalizationIntegrityError("externalization operation does not belong to this finding")

    errors: list[str] = []
    warnings: list[str] = []
    states = [str(item.get("state") or "").upper() for item in events]
    if states[0] != "STARTED":
        errors.append("AUDIT_OPERATION_DOES_NOT_START_WITH_STARTED")
    terminal_state = states[-1]
    if terminal_state not in {"STARTED", "COMPLETED", "FAILED"}:
        errors.append("AUDIT_OPERATION_TERMINAL_STATE_INVALID")
    if len(events) > 2:
        errors.append("AUDIT_OPERATION_HAS_TOO_MANY_EVENTS")
    if len(events) == 2 and terminal_state == "STARTED":
        errors.append("AUDIT_OPERATION_DUPLICATE_STARTED")

    target_values = {str(item.get("target_sha256") or "").lower() for item in events}
    if len(target_values) != 1:
        errors.append("AUDIT_OPERATION_TARGET_CHANGED")
        target = ""
    else:
        target = next(iter(target_values))
    expected_subject = f"causledger:proof-target:{target}" if target else None

    operation_archive_head, raw_archive_count = _operation_archive_head(
        attestation_archive,
        tenant_id=tenant,
        operation_id=operation,
    )
    archived: dict[str, Any] | None = None
    if raw_archive_count:
        try:
            archived = attestation_archive.operation_receipts(
                tenant_id=tenant,
                operation_id=operation,
            )
        except ProofAttestationArchiveError as exc:
            errors.append("ATTESTATION_ARCHIVE_CHAIN_INVALID")
            archived = {"archive_error_type": type(exc).__name__}

    terminal_payload = events[-1].get("payload") if isinstance(events[-1], dict) else None
    payload = terminal_payload if isinstance(terminal_payload, dict) else {}

    if terminal_state == "COMPLETED":
        if len(events) != 2:
            errors.append("COMPLETED_OPERATION_AUDIT_CARDINALITY_INVALID")
        if not raw_archive_count or archived is None or "archive_error_type" in archived:
            errors.append("COMPLETED_OPERATION_RECEIPTS_MISSING_OR_INVALID")
        else:
            if archived.get("subject_ref") != expected_subject:
                errors.append("ARCHIVED_RECEIPTS_SUBJECT_MISMATCH")
            if int(archived.get("receipt_count") or 0) != int(payload.get("attestation_archive_receipt_count") or 0):
                errors.append("ARCHIVED_RECEIPT_COUNT_MISMATCH")
            if archived.get("receipts_sha256") != payload.get("external_attestations_sha256"):
                errors.append("ARCHIVED_RECEIPT_SET_HASH_MISMATCH")
            if operation_archive_head != payload.get("attestation_archive_chain_head_sha256"):
                errors.append("ARCHIVED_OPERATION_HEAD_MISMATCH")
            if payload.get("receipts_durably_archived") is not True:
                errors.append("COMPLETED_OPERATION_DID_NOT_DECLARE_DURABLE_RECEIPTS")
            receipts = archived.get("receipts") or []
            if any(str(item.get("digest") or "").lower() != target for item in receipts if isinstance(item, dict)):
                errors.append("ARCHIVED_RECEIPT_TARGET_DIGEST_MISMATCH")
            if any(
                str((item.get("details") or {}).get("subject_ref") or "") != expected_subject
                for item in receipts
                if isinstance(item, dict)
            ):
                errors.append("ARCHIVED_RECEIPT_TARGET_SUBJECT_MISMATCH")
    elif terminal_state == "FAILED":
        if len(events) != 2:
            errors.append("FAILED_OPERATION_AUDIT_CARDINALITY_INVALID")
        if raw_archive_count:
            warnings.append("FAILED_OPERATION_HAS_ARCHIVED_RECEIPTS_REQUIRING_RECONCILIATION")
    else:
        warnings.append("EXTERNALIZATION_OPERATION_IS_INCOMPLETE")
        if raw_archive_count:
            warnings.append("INCOMPLETE_OPERATION_HAS_ARCHIVED_RECEIPTS_REQUIRING_RECONCILIATION")

    current_subject_chain_head = None
    if archived is not None and "archive_error_type" not in archived:
        current_subject_chain_head = archived.get("archive_chain_head_sha256")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "tenant_id": tenant,
        "finding_id": finding,
        "operation_id": operation,
        "operation_state": terminal_state,
        "target_sha256": target,
        "subject_ref": expected_subject,
        "audit_chain_valid": bool(audit.get("chain_valid")),
        "audit_event_count": len(events),
        "receipts_present": bool(raw_archive_count),
        "receipt_count": raw_archive_count,
        "operation_archive_chain_head_sha256": operation_archive_head,
        "current_subject_archive_chain_head_sha256": current_subject_chain_head,
        "later_subject_receipts_do_not_invalidate_operation_head": True,
        "operation_completed_does_not_imply_proof_verified": True,
    }
