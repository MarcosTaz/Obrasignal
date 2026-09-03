from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.proof import ExternalAttestation, sha256_hex


_VERIFIED_STATES = {"VERIFIED", "VALID"}
_TIMESTAMP_PURPOSE = "CHANGE_CAPTURE_SNAPSHOT_EXISTENCE_TIME"


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def _parse_aware(value: object, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise AssuranceStoreError(f"durable change chronology {label} is invalid") from exc
    if parsed.tzinfo is None:
        raise AssuranceStoreError(f"durable change chronology {label} lacks timezone")
    return parsed.astimezone(timezone.utc)


def _digest(value: object, *, label: str = "digest") -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise AssuranceStoreError(f"durable change chronology {label} is invalid")
    return text


def _verify_fact_chain(rows: list[sqlite3.Row]) -> str | None:
    previous: str | None = None
    for index, row in enumerate(rows):
        body = {
            "fact_id": row["fact_id"],
            "tenant_id": row["tenant_id"],
            "finding_id": row["finding_id"],
            "fact_type": row["fact_type"],
            "fact_text": row["fact_text"],
            "source_ref": row["source_ref"],
            "actor_id": row["actor_id"],
            "recorded_at": row["recorded_at"],
            "previous_fact_hash": row["previous_fact_hash"],
        }
        if row["previous_fact_hash"] != previous:
            raise AssuranceStoreError(f"durable change chronology fact {index} previous hash mismatch")
        expected = sha256_hex(body)
        if str(row["fact_hash"]) != expected:
            raise AssuranceStoreError(f"durable change chronology fact {index} hash mismatch")
        previous = str(row["fact_hash"])
    return previous


def _render_current_sheet(
    *,
    window: sqlite3.Row,
    facts: list[sqlite3.Row],
    window_state: str,
) -> tuple[str, str, str | None, str]:
    requested = [row for row in facts if row["fact_type"] == "REQUESTED_CHANGE"]
    requested_at = [row for row in facts if row["fact_type"] == "CHANGE_REQUESTED_AT"]
    requested_change = str(requested[-1]["fact_text"]) if requested else str(window["event_ref"])
    requested_source = "DECLARED_FACT" if requested else "EVENT_REFERENCE_FALLBACK"
    declared_requested_at = str(requested_at[-1]["fact_text"]) if requested_at else None
    factual_lines: list[str] = []
    for row in facts:
        if row["fact_type"] in {"REQUESTED_CHANGE", "CHANGE_REQUESTED_AT"}:
            continue
        source = f" | source: {row['source_ref']}" if row["source_ref"] else ""
        factual_lines.append(f"- {row['fact_type']}: {row['fact_text']}{source}")
    if not factual_lines:
        factual_lines.append("- No additional factual entries recorded.")
    lines = [
        "CAUSLEDGER — CHANGE CAPTURE SHEET",
        "",
        f"Sheet ID: {window['sheet_id']}",
        f"Change reference: {window['event_ref']}",
        f"Requested change: {requested_change}",
        f"Declared request date/time: {declared_requested_at or 'NOT DECLARED'}",
        f"CausLedger first recorded at: {window['recorded_at']}",
        f"Factual input window closes at: {window['factual_window_closes_at']}",
        f"Factual window status at download: {window_state}",
        "",
        "FACTUAL NOTES",
        *factual_lines,
        "",
        "TRUTH BOUNDARY",
        "This is a contemporaneous factual capture aid. It is not a contractual notice deadline,",
        "does not prove customer responsibility, and does not establish legal recoverability.",
        "The declared request date/time remains a declared fact unless supported by external evidence.",
    ]
    body = "\n".join(lines).rstrip() + "\n"
    return requested_change, requested_source, declared_requested_at, sha256_hex(body.encode("utf-8"))


def _validate_timestamp_row(row: sqlite3.Row) -> dict[str, Any]:
    digest = _digest(row["sheet_sha256"], label="timestamp sheet digest")
    sheet_id = str(row["sheet_id"] or "").strip()
    expected_subject = f"causledger:change-sheet:{sheet_id}:{digest}"
    if str(row["subject_ref"] or "").strip() != expected_subject:
        raise AssuranceStoreError("durable change chronology timestamp subject binding mismatch")
    try:
        details = json.loads(str(row["details_json"]))
    except (TypeError, ValueError) as exc:
        raise AssuranceStoreError("durable change chronology timestamp details are invalid") from exc
    if not isinstance(details, dict):
        raise AssuranceStoreError("durable change chronology timestamp details are invalid")
    try:
        attestation = ExternalAttestation(
            kind=str(row["kind"]),
            provider=str(row["provider"]),
            state=str(row["state"]),
            digest_algorithm=str(row["digest_algorithm"]),
            digest=digest,
            provider_ref=row["provider_ref"],
            issued_at=row["issued_at"],
            validation_ref=row["validation_ref"],
            details=details,
        )
    except ValueError as exc:
        raise AssuranceStoreError("durable change chronology timestamp envelope is invalid") from exc
    if attestation.kind != "QUALIFIED_TIMESTAMP" or attestation.digest_algorithm.upper() != "SHA-256":
        raise AssuranceStoreError("durable change chronology timestamp type is invalid")
    if attestation.verified:
        if str(details.get("subject_ref") or "").strip() != expected_subject:
            raise AssuranceStoreError("durable change chronology verified timestamp subject is invalid")
        if str(details.get("purpose") or "").strip() != _TIMESTAMP_PURPOSE:
            raise AssuranceStoreError("durable change chronology verified timestamp purpose is invalid")
        if not str(attestation.provider_ref or "").strip() or not str(attestation.issued_at or "").strip() or not str(attestation.validation_ref or "").strip():
            raise AssuranceStoreError("durable change chronology verified timestamp lacks validation material")
    body = {
        "tenant_id": str(row["tenant_id"]),
        "finding_id": str(row["finding_id"]),
        "sheet_id": sheet_id,
        "sheet_sha256": digest,
        "subject_ref": expected_subject,
        "attestation": attestation.as_dict(),
        "recorded_at": str(row["recorded_at"]),
    }
    expected_hash = sha256_hex(body)
    if str(row["attestation_hash"]) != expected_hash:
        raise AssuranceStoreError("durable change chronology timestamp receipt hash mismatch")
    if str(row["attestation_id"]) != f"sheettsa_{expected_hash[:24]}":
        raise AssuranceStoreError("durable change chronology timestamp receipt identity mismatch")
    return {
        "attestation_id": str(row["attestation_id"]),
        "sheet_sha256": digest,
        "kind": attestation.kind,
        "provider": attestation.provider,
        "state": str(attestation.state).upper(),
        "digest_algorithm": attestation.digest_algorithm.upper(),
        "provider_ref": attestation.provider_ref,
        "issued_at": attestation.issued_at,
        "validation_ref": attestation.validation_ref,
        "recorded_at": str(row["recorded_at"]),
    }


def _read_time_trust(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    finding_id: str,
    sheet_id: str,
    current_digest: str,
) -> dict[str, Any]:
    if not _table_exists(conn, "causledger_change_sheet_attestations"):
        return {
            "sheet_id": sheet_id,
            "current_snapshot_sha256": current_digest,
            "current_subject_ref": f"causledger:change-sheet:{sheet_id}:{current_digest}",
            "current_timestamp": None,
            "current_snapshot_externally_timestamped": False,
            "historical_attested_snapshot_count": 0,
            "stale_attestation_exists_for_older_snapshot": False,
            "timestamp_receipts_revalidated_on_read": True,
            "timestamp_is_digest_specific": True,
            "new_fact_requires_new_timestamp": True,
            "qualified_timestamp_claim_is_fail_closed": True,
            "persisted_attestation_state": "NO_PERSISTED_ATTESTATIONS",
            "declared_change_requested_at_is_not_upgraded_by_sheet_timestamp": True,
        }
    rows = list(conn.execute(
        """SELECT * FROM causledger_change_sheet_attestations
           WHERE tenant_id=? AND finding_id=? ORDER BY recorded_at,attestation_id""",
        (tenant_id, finding_id),
    ).fetchall())
    validated = [(row, _validate_timestamp_row(row)) for row in rows]
    current = [(row, public) for row, public in validated if str(row["sheet_sha256"]) == current_digest]
    verified = [(row, public) for row, public in current if str(row["state"]).upper() in _VERIFIED_STATES]
    latest_public = verified[-1][1] if verified else (current[-1][1] if current else None)
    historical = {str(row["sheet_sha256"]) for row, _public in validated if str(row["sheet_sha256"]) != current_digest}
    return {
        "sheet_id": sheet_id,
        "current_snapshot_sha256": current_digest,
        "current_subject_ref": f"causledger:change-sheet:{sheet_id}:{current_digest}",
        "current_timestamp": latest_public,
        "current_snapshot_externally_timestamped": bool(verified),
        "historical_attested_snapshot_count": len(historical),
        "stale_attestation_exists_for_older_snapshot": bool(historical),
        "timestamp_receipts_revalidated_on_read": True,
        "timestamp_is_digest_specific": True,
        "new_fact_requires_new_timestamp": True,
        "qualified_timestamp_claim_is_fail_closed": True,
        "persisted_attestation_state": "PRESENT" if rows else "EMPTY",
        "declared_change_requested_at_is_not_upgraded_by_sheet_timestamp": True,
    }


def _verify_supplements(rows: list[sqlite3.Row]) -> str | None:
    previous: str | None = None
    for index, row in enumerate(rows):
        body = {
            "supplement_id": row["supplement_id"],
            "tenant_id": row["tenant_id"],
            "finding_id": row["finding_id"],
            "fact_text": row["fact_text"],
            "source_ref": row["source_ref"],
            "reason_for_late_entry": row["reason_for_late_entry"],
            "declared_event_at": row["declared_event_at"],
            "actor_id": row["actor_id"],
            "recorded_at": row["recorded_at"],
            "previous_supplement_hash": row["previous_supplement_hash"],
        }
        if row["previous_supplement_hash"] != previous:
            raise AssuranceStoreError(f"durable change chronology late supplement {index} previous hash mismatch")
        expected = sha256_hex(body)
        if str(row["supplement_hash"]) != expected:
            raise AssuranceStoreError(f"durable change chronology late supplement {index} hash mismatch")
        previous = str(row["supplement_hash"])
    return previous


def _read_supplements(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    finding_id: str,
    window_state: str,
) -> dict[str, Any]:
    if not _table_exists(conn, "causledger_change_late_supplements"):
        rows: list[sqlite3.Row] = []
    else:
        rows = list(conn.execute(
            """SELECT * FROM causledger_change_late_supplements
               WHERE tenant_id=? AND finding_id=? ORDER BY recorded_at,supplement_id""",
            (tenant_id, finding_id),
        ).fetchall())
    head = _verify_supplements(rows)
    return {
        "finding_id": finding_id,
        "available": window_state == "CLOSED",
        "contemporaneous_window_state": window_state,
        "count": len(rows),
        "chain_head_sha256": head,
        "supplements": [
            {
                "supplement_id": str(row["supplement_id"]),
                "fact_text": str(row["fact_text"]),
                "source_ref": row["source_ref"],
                "reason_for_late_entry": str(row["reason_for_late_entry"]),
                "declared_event_at": row["declared_event_at"],
                "recorded_at": str(row["recorded_at"]),
                "supplement_hash": str(row["supplement_hash"]),
                "classification": "LATE_SUPPLEMENT",
            }
            for row in rows
        ],
        "late_supplement_does_not_reopen_contemporaneous_window": True,
        "late_supplement_is_not_backdated": True,
    }


def read_change_chronology(
    database: str | Path,
    *,
    tenant_id: str,
    finding_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Reconstruct change chronology using SELECT-only durable truth.

    This reader never creates schema, writes receipts, repairs missing tables, or
    requests external attestations. Missing optional proof tables remain explicit
    absence of proof. Partial mandatory capture schema fails closed.
    """
    path = Path(database)
    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        with conn:
            if not _table_exists(conn, "causledger_change_capture_windows"):
                return {
                    "state": "NOT_CAPTURED",
                    "change_capture_available": False,
                    "absence_does_not_establish_no_change": True,
                    "reader_side_effect_free": True,
                }
            window = conn.execute(
                """SELECT * FROM causledger_change_capture_windows
                   WHERE tenant_id=? AND finding_id=?""",
                (tenant_id, finding_id),
            ).fetchone()
            if window is None:
                return {
                    "state": "NOT_CAPTURED",
                    "change_capture_available": False,
                    "absence_does_not_establish_no_change": True,
                    "reader_side_effect_free": True,
                }
            for required_table in ("causledger_change_facts", "causledger_change_sheet_downloads"):
                if not _table_exists(conn, required_table):
                    raise AssuranceStoreError(f"durable change chronology mandatory table missing: {required_table}")
            facts = list(conn.execute(
                """SELECT * FROM causledger_change_facts
                   WHERE tenant_id=? AND finding_id=? ORDER BY recorded_at,fact_id""",
                (tenant_id, finding_id),
            ).fetchall())
            chain_head = _verify_fact_chain(facts)
            closes_at = _parse_aware(window["factual_window_closes_at"], label="factual window close")
            window_state = "OPEN" if current_time <= closes_at else "CLOSED"
            requested_change, requested_source, declared_requested_at, current_digest = _render_current_sheet(
                window=window,
                facts=facts,
                window_state=window_state,
            )
            export_count = int(conn.execute(
                """SELECT COUNT(*) AS n FROM causledger_change_sheet_downloads
                   WHERE tenant_id=? AND finding_id=?""",
                (tenant_id, finding_id),
            ).fetchone()["n"])
            trust = _read_time_trust(
                conn,
                tenant_id=tenant_id,
                finding_id=finding_id,
                sheet_id=str(window["sheet_id"]),
                current_digest=current_digest,
            )
            supplements = _read_supplements(
                conn,
                tenant_id=tenant_id,
                finding_id=finding_id,
                window_state=window_state,
            )
    except sqlite3.DatabaseError as exc:
        raise AssuranceStoreError("durable change chronology database read failed") from exc
    finally:
        try:
            conn.close()
        except (UnboundLocalError, AttributeError):
            pass

    return {
        "state": "CAPTURED",
        "change_capture_available": True,
        "sheet_id": str(window["sheet_id"]),
        "event_ref": str(window["event_ref"]),
        "requested_change": requested_change,
        "requested_change_source": requested_source,
        "declared_change_requested_at": declared_requested_at,
        "declared_change_requested_at_is_externally_verified": False,
        "causledger_first_recorded_at": str(window["recorded_at"]),
        "factual_window_closes_at": str(window["factual_window_closes_at"]),
        "factual_window_hours": int(window["factual_window_hours"]),
        "window_state_at_pack_generation": window_state,
        "fact_count": len(facts),
        "fact_chain_head_sha256": chain_head,
        "current_sheet_sha256": current_digest,
        "export_generation_count": export_count,
        "current_snapshot_time_trust": trust,
        "late_supplements": supplements,
        "reader_side_effect_free": True,
        "chronology_truth_boundaries": {
            "operational_capture_window_is_not_contractual_notice_deadline": True,
            "declared_event_time_is_not_backdated_server_time": True,
            "late_supplement_does_not_rewrite_contemporaneous_sheet": True,
            "change_capture_does_not_establish_customer_responsibility": True,
            "change_capture_does_not_establish_legal_recoverability": True,
        },
    }
