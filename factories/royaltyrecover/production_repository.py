from __future__ import annotations

import hmac
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from secure_repository import BACKUP_MAGIC, SecureRoyaltyRepository


class ProductionRoyaltyRepository(SecureRoyaltyRepository):
    """Final production repository boundary.

    Restore deliberately emits no synthetic organization event. The restored
    audit chain is verified exactly as it existed in the backup; operational
    restore logging belongs outside the tenant ledger (deployment/runbook log).
    """

    def verify_audit_chain(self) -> bool:
        rows = self.conn.execute(
            """SELECT e.id, e.organization_id, e.actor_id, e.event_type, e.entity_type,
                      e.entity_id, e.event_at, e.payload_json, i.prev_hash, i.event_hash
               FROM audit_integrity i JOIN audit_events e ON e.id=i.audit_event_id
               ORDER BY i.rowid ASC"""
        ).fetchall()
        event_count = self.conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        if event_count != len(rows):
            return False
        previous = "GENESIS"
        for row in rows:
            if row["prev_hash"] != previous:
                return False
            event = {
                "id": row["id"],
                "organization_id": row["organization_id"],
                "actor_id": row["actor_id"],
                "event_type": row["event_type"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "event_at": row["event_at"],
                "payload_json": row["payload_json"],
            }
            expected = self._event_hash(event, previous)
            if not hmac.compare_digest(str(row["event_hash"]), expected):
                return False
            previous = str(row["event_hash"])
        return True

    def restore_encrypted_from(self, source_path: str | Path, *, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("AES256_KEY_REQUIRED")
        blob = Path(source_path).read_bytes()
        offset = len(BACKUP_MAGIC)
        if len(blob) <= offset + 12 or not blob.startswith(BACKUP_MAGIC):
            raise ValueError("INVALID_ENCRYPTED_BACKUP")
        nonce = blob[offset:offset + 12]
        try:
            plain = AESGCM(key).decrypt(nonce, blob[offset + 12 :], BACKUP_MAGIC)
        except Exception as exc:
            raise ValueError("BACKUP_DECRYPTION_FAILED") from exc
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            source = Path(tmp.name)
            tmp.write(plain)
        try:
            with closing(sqlite3.connect(str(source))) as restored:
                check = restored.execute("PRAGMA integrity_check").fetchone()
                if not check or check[0] != "ok":
                    raise ValueError("BACKUP_INTEGRITY_FAILED")
                restored.backup(self.conn)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            if not self.integrity_check() or not self.verify_audit_chain():
                raise ValueError("RESTORE_VERIFICATION_FAILED")
        finally:
            source.unlink(missing_ok=True)
