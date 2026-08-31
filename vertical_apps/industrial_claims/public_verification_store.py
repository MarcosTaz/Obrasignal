from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from vertical_apps.industrial_claims.proof import canonical_json_bytes, sha256_hex


class PublicVerificationStoreError(RuntimeError):
    pass


def _required(value: object, *, label: str, max_chars: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > max_chars or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise PublicVerificationStoreError(f"invalid {label}")
    return text


def _token_hash(verification_id: str) -> str:
    token = _required(verification_id, label="verification_id", max_chars=128)
    return sha256_hex(token.encode("utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PublicVerificationStore:
    """Append-only registry for privacy-minimized public proof receipts.

    The immutable receipt represents what was published at issuance. Later
    lifecycle changes are separate hash-chained events. No lifecycle transition
    rewrites the original receipt or exposes tenant/case metadata publicly.
    """

    def __init__(self, database: str | Path) -> None:
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS causledger_public_receipts(
                    token_hash TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    subject_ref TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    receipt_sha256 TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    published_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS causledger_public_receipt_events(
                    event_id TEXT PRIMARY KEY,
                    token_hash TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    successor_token_hash TEXT,
                    reason TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    previous_event_hash TEXT,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE INDEX IF NOT EXISTS idx_causledger_public_events
                    ON causledger_public_receipt_events(token_hash,occurred_at,event_id);
                CREATE TRIGGER IF NOT EXISTS causledger_public_receipts_no_update
                    BEFORE UPDATE ON causledger_public_receipts BEGIN SELECT RAISE(ABORT,'public verification receipts are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causledger_public_receipts_no_delete
                    BEFORE DELETE ON causledger_public_receipts BEGIN SELECT RAISE(ABORT,'public verification receipts are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causledger_public_events_no_update
                    BEFORE UPDATE ON causledger_public_receipt_events BEGIN SELECT RAISE(ABORT,'public verification lifecycle is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causledger_public_events_no_delete
                    BEFORE DELETE ON causledger_public_receipt_events BEGIN SELECT RAISE(ABORT,'public verification lifecycle is append-only'); END;
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _validated_receipt(row: sqlite3.Row, *, label: str) -> dict[str, Any]:
        try:
            receipt = json.loads(str(row["receipt_json"]))
        except (TypeError, ValueError) as exc:
            raise PublicVerificationStoreError(f"stored {label} public receipt is invalid") from exc
        if not isinstance(receipt, dict):
            raise PublicVerificationStoreError(f"stored {label} public receipt is invalid")
        body = dict(receipt)
        stored = str(body.pop("receipt_sha256", "") or "")
        if stored != row["receipt_sha256"] or stored != sha256_hex(body):
            raise PublicVerificationStoreError(f"stored {label} public receipt integrity failure")
        return receipt

    def publish(
        self,
        *,
        tenant_id: str,
        subject_ref: str,
        receipt: Mapping[str, Any],
        actor_id: str,
    ) -> None:
        tenant = _required(tenant_id, label="tenant_id", max_chars=128)
        subject = _required(subject_ref, label="subject_ref")
        actor = _required(actor_id, label="actor_id", max_chars=256)
        verification_id = _required(receipt.get("verification_id"), label="verification_id", max_chars=128)
        if (receipt.get("lifecycle") or {}).get("state") != "CURRENT":
            raise PublicVerificationStoreError("only a CURRENT immutable receipt may be initially published")
        token_hash = _token_hash(verification_id)
        body = dict(receipt)
        stored_digest = str(body.pop("receipt_sha256", "") or "").strip().lower()
        expected_digest = sha256_hex(body)
        if stored_digest != expected_digest:
            raise PublicVerificationStoreError("public receipt integrity check failed before publication")
        receipt_json = canonical_json_bytes(dict(receipt)).decode("utf-8")
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT token_hash FROM causledger_public_receipts WHERE token_hash=?",
                (token_hash,),
            ).fetchone()
            if existing is not None:
                raise PublicVerificationStoreError("public verification id already exists")
            conn.execute(
                """INSERT INTO causledger_public_receipts(
                    token_hash,tenant_id,subject_ref,receipt_json,receipt_sha256,actor_id,published_at
                ) VALUES(?,?,?,?,?,?,?)""",
                (token_hash, tenant, subject, receipt_json, stored_digest, actor, _utc_now()),
            )

    def _events(self, conn: sqlite3.Connection, token_hash: str) -> list[sqlite3.Row]:
        return list(conn.execute(
            """SELECT * FROM causledger_public_receipt_events
               WHERE token_hash=? ORDER BY occurred_at,event_id""",
            (token_hash,),
        ).fetchall())

    def _verify_event_chain(self, rows: list[sqlite3.Row]) -> tuple[bool, str | None, list[str]]:
        previous: str | None = None
        errors: list[str] = []
        for index, row in enumerate(rows):
            body = {
                "event_id": row["event_id"],
                "token_hash": row["token_hash"],
                "event_type": row["event_type"],
                "successor_token_hash": row["successor_token_hash"],
                "reason": row["reason"],
                "actor_id": row["actor_id"],
                "occurred_at": row["occurred_at"],
                "previous_event_hash": row["previous_event_hash"],
            }
            if row["previous_event_hash"] != previous:
                errors.append(f"EVENT_{index}_PREVIOUS_HASH_MISMATCH")
            expected = sha256_hex(body)
            if row["event_hash"] != expected:
                errors.append(f"EVENT_{index}_HASH_MISMATCH")
            previous = str(row["event_hash"])
        return not errors, previous, errors

    def transition(
        self,
        *,
        tenant_id: str,
        verification_id: str,
        event_id: str,
        event_type: str,
        reason: str,
        actor_id: str,
        successor_verification_id: str | None = None,
    ) -> None:
        tenant = _required(tenant_id, label="tenant_id", max_chars=128)
        token_hash = _token_hash(verification_id)
        event_key = _required(event_id, label="event_id")
        transition = _required(event_type, label="event_type", max_chars=64).upper()
        if transition not in {"SUPERSEDED", "WITHDRAWN"}:
            raise PublicVerificationStoreError("unsupported public verification lifecycle transition")
        actor = _required(actor_id, label="actor_id", max_chars=256)
        transition_reason = _required(reason, label="reason")
        successor_hash = None
        if transition == "SUPERSEDED":
            if not successor_verification_id:
                raise PublicVerificationStoreError("SUPERSEDED transition requires successor verification id")
            successor_hash = _token_hash(successor_verification_id)
            if successor_hash == token_hash:
                raise PublicVerificationStoreError("public verification receipt cannot supersede itself")
        elif successor_verification_id is not None:
            raise PublicVerificationStoreError("WITHDRAWN transition cannot declare successor")

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT tenant_id FROM causledger_public_receipts WHERE token_hash=?",
                (token_hash,),
            ).fetchone()
            if current is None:
                raise PublicVerificationStoreError("public verification receipt not found")
            if str(current["tenant_id"]) != tenant:
                raise PublicVerificationStoreError("public verification receipt does not belong to authenticated tenant")
            if successor_hash is not None:
                successor = conn.execute(
                    "SELECT tenant_id FROM causledger_public_receipts WHERE token_hash=?",
                    (successor_hash,),
                ).fetchone()
                if successor is None:
                    raise PublicVerificationStoreError("successor public verification receipt not found")
                if successor["tenant_id"] != tenant:
                    raise PublicVerificationStoreError("cross-tenant public receipt supersession rejected")
            rows = self._events(conn, token_hash)
            valid, previous, errors = self._verify_event_chain(rows)
            if not valid:
                raise PublicVerificationStoreError(f"public verification lifecycle chain invalid: {errors}")
            if rows:
                raise PublicVerificationStoreError("public verification receipt already has a terminal lifecycle transition")
            occurred_at = _utc_now()
            event_body = {
                "event_id": event_key,
                "token_hash": token_hash,
                "event_type": transition,
                "successor_token_hash": successor_hash,
                "reason": transition_reason,
                "actor_id": actor,
                "occurred_at": occurred_at,
                "previous_event_hash": previous,
            }
            conn.execute(
                """INSERT INTO causledger_public_receipt_events(
                    event_id,token_hash,event_type,successor_token_hash,reason,actor_id,
                    occurred_at,previous_event_hash,event_hash
                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    event_key,
                    token_hash,
                    transition,
                    successor_hash,
                    transition_reason,
                    actor,
                    occurred_at,
                    previous,
                    sha256_hex(event_body),
                ),
            )
            conn.commit()

    def get_public(self, verification_id: str) -> dict[str, Any]:
        token_hash = _token_hash(verification_id)
        successor_verification_id: str | None = None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT receipt_json,receipt_sha256 FROM causledger_public_receipts WHERE token_hash=?",
                (token_hash,),
            ).fetchone()
            if row is None:
                raise PublicVerificationStoreError("public verification receipt not found")
            receipt = self._validated_receipt(row, label="current")
            events = self._events(conn, token_hash)
            if events and events[-1]["successor_token_hash"]:
                successor_row = conn.execute(
                    "SELECT receipt_json,receipt_sha256 FROM causledger_public_receipts WHERE token_hash=?",
                    (events[-1]["successor_token_hash"],),
                ).fetchone()
                if successor_row is None:
                    raise PublicVerificationStoreError("public successor receipt lineage is missing")
                successor_receipt = self._validated_receipt(successor_row, label="successor")
                successor_verification_id = _required(
                    successor_receipt.get("verification_id"),
                    label="successor verification_id",
                    max_chars=128,
                )
                if _token_hash(successor_verification_id) != events[-1]["successor_token_hash"]:
                    raise PublicVerificationStoreError("public successor receipt token binding failed")
        valid, chain_head, errors = self._verify_event_chain(events)
        if not valid:
            raise PublicVerificationStoreError(f"public lifecycle integrity failure: {errors}")
        status = "CURRENT"
        if events:
            status = str(events[-1]["event_type"])
        return {
            "receipt": receipt,
            "current_lifecycle": {
                "state": status,
                "successor_verification_id": successor_verification_id,
                "successor_verification_path": f"/verify/{successor_verification_id}" if successor_verification_id else None,
                "event_chain_head_sha256": chain_head,
            },
            "privacy": {
                "tenant_identifier_exposed": False,
                "case_identifier_exposed": False,
                "document_content_exposed": False,
                "economic_amount_exposed": False,
            },
        }
