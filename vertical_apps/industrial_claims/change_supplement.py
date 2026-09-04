from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from vertical_apps.industrial_claims.change_capture import ChangeCaptureStore
from vertical_apps.industrial_claims.proof import sha256_hex


class ChangeSupplementError(RuntimeError):
    pass


MAX_TEXT_CHARS = 4000
MAX_REASON_CHARS = 2000
MAX_SOURCE_CHARS = 512


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _required(value: object, *, label: str, max_chars: int) -> str:
    raw = str(value or "")
    if any((ord(ch) < 32 or ord(ch) == 127) and ch not in {"\n", "\r", "\t"} for ch in raw):
        raise ChangeSupplementError(f"invalid {label}")
    text = raw.strip()
    if not text or len(text) > max_chars:
        raise ChangeSupplementError(f"invalid {label}")
    return text


def _aware_iso(value: object, *, label: str) -> str:
    text = _required(value, label=label, max_chars=128)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ChangeSupplementError(f"invalid {label}") from exc
    if parsed.tzinfo is None:
        raise ChangeSupplementError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc).isoformat()


class LateChangeSupplementStore:
    """Append-only late factual supplements kept outside the contemporaneous sheet."""

    def __init__(
        self,
        database: str | Path,
        *,
        capture_store: ChangeCaptureStore,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self.path = Path(database)
        self.capture_store = capture_store
        self.clock = clock
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS causledger_change_late_supplements(
                    supplement_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    finding_id TEXT NOT NULL,
                    fact_text TEXT NOT NULL,
                    source_ref TEXT,
                    reason_for_late_entry TEXT NOT NULL,
                    declared_event_at TEXT,
                    actor_id TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    previous_supplement_hash TEXT,
                    supplement_hash TEXT NOT NULL UNIQUE
                );
                CREATE INDEX IF NOT EXISTS idx_causledger_change_late_supplements_case
                    ON causledger_change_late_supplements(tenant_id,finding_id,recorded_at,supplement_id);
                CREATE TRIGGER IF NOT EXISTS causledger_change_late_supplements_no_update
                    BEFORE UPDATE ON causledger_change_late_supplements
                    BEGIN SELECT RAISE(ABORT,'late change supplements are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causledger_change_late_supplements_no_delete
                    BEFORE DELETE ON causledger_change_late_supplements
                    BEGIN SELECT RAISE(ABORT,'late change supplements are append-only'); END;
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _rows(self, conn: sqlite3.Connection, *, tenant_id: str, finding_id: str) -> list[sqlite3.Row]:
        return list(
            conn.execute(
                """SELECT * FROM causledger_change_late_supplements
                   WHERE tenant_id=? AND finding_id=? ORDER BY recorded_at,supplement_id""",
                (tenant_id, finding_id),
            ).fetchall()
        )

    @staticmethod
    def _verify(rows: list[sqlite3.Row]) -> tuple[bool, str | None, list[str]]:
        previous = None
        errors: list[str] = []
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
                errors.append(f"SUPPLEMENT_{index}_PREVIOUS_HASH_MISMATCH")
            expected = sha256_hex(body)
            if str(row["supplement_hash"]) != expected:
                errors.append(f"SUPPLEMENT_{index}_HASH_MISMATCH")
            previous = str(row["supplement_hash"])
        return not errors, previous, errors

    def add(
        self,
        *,
        tenant_id: str,
        finding_id: str,
        actor_id: str,
        fact_text: str,
        reason_for_late_entry: str,
        source_ref: str | None = None,
        declared_event_at: str | None = None,
    ) -> dict[str, Any]:
        tenant = _required(tenant_id, label="tenant_id", max_chars=64)
        finding = _required(finding_id, label="finding_id", max_chars=2048)
        actor = _required(actor_id, label="actor_id", max_chars=256)
        text = _required(fact_text, label="fact_text", max_chars=MAX_TEXT_CHARS)
        reason = _required(reason_for_late_entry, label="reason_for_late_entry", max_chars=MAX_REASON_CHARS)
        source = None if source_ref is None else _required(source_ref, label="source_ref", max_chars=MAX_SOURCE_CHARS)
        declared = None if declared_event_at is None else _aware_iso(declared_event_at, label="declared_event_at")
        capture = self.capture_store.status(tenant_id=tenant, finding_id=finding)
        if capture["window_state"] != "CLOSED":
            raise ChangeSupplementError("late supplement is only available after the contemporaneous factual window closes")
        supplement_id = f"late_{secrets.token_urlsafe(18)}"
        now = self.clock()
        if now.tzinfo is None:
            raise ChangeSupplementError("internal supplement clock must be timezone-aware")
        recorded_at = now.astimezone(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = self._rows(conn, tenant_id=tenant, finding_id=finding)
            valid, previous, errors = self._verify(rows)
            if not valid:
                raise ChangeSupplementError(f"late supplement chain integrity failure: {errors}")
            body = {
                "supplement_id": supplement_id,
                "tenant_id": tenant,
                "finding_id": finding,
                "fact_text": text,
                "source_ref": source,
                "reason_for_late_entry": reason,
                "declared_event_at": declared,
                "actor_id": actor,
                "recorded_at": recorded_at,
                "previous_supplement_hash": previous,
            }
            digest = sha256_hex(body)
            conn.execute(
                """INSERT INTO causledger_change_late_supplements(
                    supplement_id,tenant_id,finding_id,fact_text,source_ref,reason_for_late_entry,
                    declared_event_at,actor_id,recorded_at,previous_supplement_hash,supplement_hash
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    supplement_id,
                    tenant,
                    finding,
                    text,
                    source,
                    reason,
                    declared,
                    actor,
                    recorded_at,
                    previous,
                    digest,
                ),
            )
            conn.commit()
        return {**body, "supplement_hash": digest, "classification": "LATE_SUPPLEMENT"}

    def status(self, *, tenant_id: str, finding_id: str) -> dict[str, Any]:
        tenant = _required(tenant_id, label="tenant_id", max_chars=64)
        finding = _required(finding_id, label="finding_id", max_chars=2048)
        capture = self.capture_store.status(tenant_id=tenant, finding_id=finding)
        with self._connect() as conn:
            rows = self._rows(conn, tenant_id=tenant, finding_id=finding)
        valid, head, errors = self._verify(rows)
        if not valid:
            raise ChangeSupplementError(f"late supplement chain integrity failure: {errors}")
        return {
            "finding_id": finding,
            "available": capture["window_state"] == "CLOSED",
            "contemporaneous_window_state": capture["window_state"],
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

    def render_sheet(self, *, tenant_id: str, finding_id: str) -> tuple[str, str]:
        status = self.status(tenant_id=tenant_id, finding_id=finding_id)
        lines = [
            "VINDORUM — LATE CHANGE SUPPLEMENT",
            "",
            f"Finding reference: {status['finding_id']}",
            "Classification: LATE_SUPPLEMENT",
            "",
            "This document contains information recorded after the contemporaneous factual capture window closed.",
            "It does not rewrite, extend, or backdate the original Change Capture Sheet.",
            "",
        ]
        if not status["supplements"]:
            lines.append("No late supplements recorded.")
        for item in status["supplements"]:
            lines.extend(
                [
                    f"Supplement ID: {item['supplement_id']}",
                    f"Recorded at: {item['recorded_at']}",
                    f"Declared event at: {item['declared_event_at'] or 'NOT DECLARED'}",
                    f"Fact: {item['fact_text']}",
                    f"Reason late: {item['reason_for_late_entry']}",
                    f"Source: {item['source_ref'] or 'NOT PROVIDED'}",
                    f"Supplement SHA-256: {item['supplement_hash']}",
                    "",
                ]
            )
        body = "\n".join(lines).rstrip() + "\n"
        digest = sha256_hex(body.encode("utf-8"))
        return body + f"\nSupplement sheet SHA-256: {digest}\n", digest
