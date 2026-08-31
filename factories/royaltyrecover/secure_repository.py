from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from repository import RoyaltyRepository, _id, _now, _required_text


BACKUP_MAGIC = b"ROYALTYRECOVER1"


class SecureRoyaltyRepository(RoyaltyRepository):
    """RoyaltyRepository with production integrity, encrypted DR and deletion.

    Raw agreement/evidence text is still never persisted by the web boundary;
    only lineage hashes and reviewed metadata enter this store.
    """

    def __init__(self, connection: sqlite3.Connection, *, audit_secret: bytes):
        if len(audit_secret) < 32:
            raise ValueError("ROYALTYRECOVER_AUDIT_SECRET must be at least 32 bytes")
        self._audit_secret = bytes(audit_secret)
        super().__init__(connection)

    @classmethod
    def memory(cls, *, audit_secret: bytes) -> "SecureRoyaltyRepository":
        conn = sqlite3.connect(":memory:")
        repo = cls(conn, audit_secret=audit_secret)
        repo.initialize()
        return repo

    @classmethod
    def file(cls, path: str, *, audit_secret: bytes) -> "SecureRoyaltyRepository":
        conn = sqlite3.connect(path, timeout=10.0)
        repo = cls(conn, audit_secret=audit_secret)
        repo.initialize()
        return repo

    def initialize(self) -> None:
        super().initialize()
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS audit_integrity (
                audit_event_id TEXT PRIMARY KEY REFERENCES audit_events(id) ON DELETE RESTRICT,
                prev_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS retention_controls (
                agreement_id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL REFERENCES organizations(id),
                purge_after TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self._backfill_audit_integrity()
        self.conn.commit()

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _event_hash(self, event: dict[str, Any], prev_hash: str) -> str:
        material = dict(event)
        material["prev_hash"] = prev_hash
        return hmac.new(self._audit_secret, self._canonical(material).encode("utf-8"), hashlib.sha256).hexdigest()

    def _backfill_audit_integrity(self) -> None:
        rows = self.conn.execute(
            "SELECT id, organization_id, actor_id, event_type, entity_type, entity_id, event_at, payload_json FROM audit_events ORDER BY event_at, id"
        ).fetchall()
        previous = "GENESIS"
        for row in rows:
            current = self.conn.execute(
                "SELECT prev_hash, event_hash FROM audit_integrity WHERE audit_event_id=?",
                (row["id"],),
            ).fetchone()
            if current:
                previous = current["event_hash"]
                continue
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
            digest = self._event_hash(event, previous)
            self.conn.execute(
                "INSERT INTO audit_integrity(audit_event_id, prev_hash, event_hash) VALUES(?,?,?)",
                (row["id"], previous, digest),
            )
            previous = digest

    def _audit(
        self,
        org_id: str,
        actor_id: str,
        event_type: str,
        entity_type: str,
        entity_id: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        event_id = _id("evt")
        event_at = _now()
        payload_json = json.dumps(payload or {}, sort_keys=True)
        previous_row = self.conn.execute(
            "SELECT event_hash FROM audit_integrity ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        previous = str(previous_row["event_hash"]) if previous_row else "GENESIS"
        event = {
            "id": event_id,
            "organization_id": org_id,
            "actor_id": _required_text(actor_id, "actor_id"),
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "event_at": event_at,
            "payload_json": payload_json,
        }
        digest = self._event_hash(event, previous)
        self.conn.execute(
            "INSERT INTO audit_events(id, organization_id, actor_id, event_type, entity_type, entity_id, event_at, payload_json) VALUES(?,?,?,?,?,?,?,?)",
            (
                event_id,
                org_id,
                event["actor_id"],
                event_type,
                entity_type,
                entity_id,
                event_at,
                payload_json,
            ),
        )
        self.conn.execute(
            "INSERT INTO audit_integrity(audit_event_id, prev_hash, event_hash) VALUES(?,?,?)",
            (event_id, previous, digest),
        )

    def verify_audit_chain(self) -> bool:
        rows = self.conn.execute(
            """SELECT e.id, e.organization_id, e.actor_id, e.event_type, e.entity_type,
                      e.entity_id, e.event_at, e.payload_json, i.prev_hash, i.event_hash
               FROM audit_events e JOIN audit_integrity i ON i.audit_event_id=e.id
               ORDER BY e.event_at, e.id"""
        ).fetchall()
        event_count = self.conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        integrity_count = self.conn.execute("SELECT COUNT(*) FROM audit_integrity").fetchone()[0]
        if event_count != integrity_count:
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

    def integrity_check(self) -> bool:
        row = self.conn.execute("PRAGMA integrity_check").fetchone()
        return bool(row and row[0] == "ok")

    def backup_encrypted_to(self, destination: str | Path, *, key: bytes) -> str:
        if len(key) != 32:
            raise ValueError("AES256_KEY_REQUIRED")
        destination = Path(destination)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            plain_path = Path(tmp.name)
        try:
            with closing(sqlite3.connect(str(plain_path))) as target:
                self.conn.backup(target)
            plain = plain_path.read_bytes()
            nonce = os.urandom(12)
            cipher = AESGCM(key).encrypt(nonce, plain, BACKUP_MAGIC)
            temp_destination = destination.with_suffix(destination.suffix + ".tmp")
            temp_destination.write_bytes(BACKUP_MAGIC + nonce + cipher)
            temp_destination.replace(destination)
        finally:
            plain_path.unlink(missing_ok=True)
        return str(destination)

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
            self._audit("SYSTEM", "system:restore", "RESTORE", "Repository", "database", {})
            self.conn.commit()
        finally:
            source.unlink(missing_ok=True)

    def schedule_retention(
        self,
        org_id: str,
        agreement_id: str,
        purge_after: str,
        reason: str,
        actor_id: str,
    ) -> dict[str, Any]:
        self.get_agreement(org_id, agreement_id)
        purge_after = _required_text(purge_after, "purge_after")
        reason = _required_text(reason, "reason")
        self.conn.execute(
            """INSERT INTO retention_controls(agreement_id, organization_id, purge_after, reason, created_at)
               VALUES(?,?,?,?,?) ON CONFLICT(agreement_id) DO UPDATE SET
               purge_after=excluded.purge_after, reason=excluded.reason""",
            (agreement_id, org_id, purge_after, reason, _now()),
        )
        self._audit(org_id, actor_id, "RETENTION_SCHEDULED", "Agreement", agreement_id, {"purge_after": purge_after, "reason": reason})
        self.conn.commit()
        return {"agreement_id": agreement_id, "purge_after": purge_after, "reason": reason}

    def purge_agreement(self, org_id: str, agreement_id: str, actor_id: str) -> dict[str, int]:
        self.get_agreement(org_id, agreement_id)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            calc_ids = [r[0] for r in self.conn.execute("SELECT id FROM calculation_runs WHERE agreement_id=?", (agreement_id,))]
            finding_ids = [r[0] for r in self.conn.execute("SELECT id FROM findings WHERE agreement_id=?", (agreement_id,))]
            sales_ids = [r[0] for r in self.conn.execute("SELECT id FROM sales_records WHERE agreement_id=?", (agreement_id,))]
            version_ids = [r[0] for r in self.conn.execute("SELECT id FROM agreement_versions WHERE agreement_id=?", (agreement_id,))]
            rule_ids = []
            clause_ids = []
            if version_ids:
                marks = ",".join("?" for _ in version_ids)
                clause_ids = [r[0] for r in self.conn.execute(f"SELECT id FROM clauses WHERE agreement_version_id IN ({marks})", version_ids)]
                rule_ids = [r[0] for r in self.conn.execute(f"SELECT id FROM royalty_rules WHERE agreement_version_id IN ({marks})", version_ids)]

            deleted: dict[str, int] = {}
            def delete(sql: str, params=()):
                cur = self.conn.execute(sql, params)
                return cur.rowcount

            if finding_ids:
                marks = ",".join("?" for _ in finding_ids)
                outcome_ids = [r[0] for r in self.conn.execute(f"SELECT id FROM outcomes WHERE finding_id IN ({marks})", finding_ids)]
                if outcome_ids:
                    omarks = ",".join("?" for _ in outcome_ids)
                    deleted["recovered_amounts"] = delete(f"DELETE FROM recovered_amounts WHERE outcome_id IN ({omarks})", outcome_ids)
                deleted["outcomes"] = delete(f"DELETE FROM outcomes WHERE finding_id IN ({marks})", finding_ids)
                deleted["claims"] = delete(f"DELETE FROM claims WHERE finding_id IN ({marks})", finding_ids)
                deleted["recovery_actions"] = delete(f"DELETE FROM recovery_actions WHERE finding_id IN ({marks})", finding_ids)
                deleted["reviews"] = delete(f"DELETE FROM reviews WHERE finding_id IN ({marks})", finding_ids)
                deleted["information_requests"] = delete(f"DELETE FROM information_requests WHERE finding_id IN ({marks})", finding_ids)
                deleted["finding_evidence"] = delete(f"DELETE FROM finding_evidence WHERE finding_id IN ({marks})", finding_ids)
                deleted["findings"] = delete(f"DELETE FROM findings WHERE id IN ({marks})", finding_ids)
            if calc_ids:
                marks = ",".join("?" for _ in calc_ids)
                deleted["variances"] = delete(f"DELETE FROM variances WHERE calculation_run_id IN ({marks})", calc_ids)
                deleted["expected_royalties"] = delete(f"DELETE FROM expected_royalties WHERE calculation_run_id IN ({marks})", calc_ids)
                deleted["calculation_runs"] = delete(f"DELETE FROM calculation_runs WHERE id IN ({marks})", calc_ids)
            if sales_ids:
                marks = ",".join("?" for _ in sales_ids)
                deleted["deductions"] = delete(f"DELETE FROM deductions WHERE sales_record_id IN ({marks})", sales_ids)
                deleted["sales_records"] = delete(f"DELETE FROM sales_records WHERE id IN ({marks})", sales_ids)
            deleted["payments"] = delete("DELETE FROM payments WHERE agreement_id=?", (agreement_id,))
            deleted["royalty_statements"] = delete("DELETE FROM royalty_statements WHERE agreement_id=?", (agreement_id,))
            deleted["sublicenses"] = delete("DELETE FROM sublicenses WHERE agreement_id=?", (agreement_id,))
            deleted["deadlines"] = delete("DELETE FROM deadlines WHERE agreement_id=?", (agreement_id,))
            if rule_ids:
                marks = ",".join("?" for _ in rule_ids)
                deleted["royalty_tiers"] = delete(f"DELETE FROM royalty_tiers WHERE royalty_rule_id IN ({marks})", rule_ids)
                deleted["royalty_rules"] = delete(f"DELETE FROM royalty_rules WHERE id IN ({marks})", rule_ids)
            if clause_ids:
                marks = ",".join("?" for _ in clause_ids)
                deleted["audit_rights"] = delete(f"DELETE FROM audit_rights WHERE clause_id IN ({marks})", clause_ids)
                deleted["clauses"] = delete(f"DELETE FROM clauses WHERE id IN ({marks})", clause_ids)
            if version_ids:
                marks = ",".join("?" for _ in version_ids)
                deleted["agreement_versions"] = delete(f"DELETE FROM agreement_versions WHERE id IN ({marks})", version_ids)
            delete("DELETE FROM retention_controls WHERE agreement_id=?", (agreement_id,))
            deleted["agreements"] = delete("DELETE FROM agreements WHERE id=?", (agreement_id,))
            self._audit(org_id, actor_id, "PURGE", "Agreement", agreement_id, {"deleted": deleted})
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        if not self.verify_audit_chain():
            raise RuntimeError("AUDIT_CHAIN_FAILED_AFTER_PURGE")
        return deleted

    def purge_due(self, org_id: str, as_of: str, actor_id: str) -> dict[str, Any]:
        rows = self.conn.execute(
            "SELECT agreement_id FROM retention_controls WHERE organization_id=? AND purge_after<=? ORDER BY agreement_id",
            (org_id, as_of),
        ).fetchall()
        ids = [str(row["agreement_id"]) for row in rows]
        results = {agreement_id: self.purge_agreement(org_id, agreement_id, actor_id) for agreement_id in ids}
        return {"purged_agreements": ids, "results": results}
