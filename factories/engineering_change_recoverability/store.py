from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


BACKUP_MAGIC = b"ECEBK1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class CaseStore:
    """Tenant-scoped append-only case and analysis history.

    Production mode additionally requires a cryptographic audit key. Operational
    case/analysis data can be purged while the minimal audit ledger is retained.
    """

    def __init__(self, path: str | Path, *, audit_secret: bytes | None = None):
        self.path = str(path)
        env_secret = os.getenv("ECE_AUDIT_SECRET", "").encode()
        self._audit_secret = audit_secret if audit_secret is not None else env_secret
        if self._audit_secret and len(self._audit_secret) < 32:
            raise ValueError("ECE_AUDIT_SECRET must be at least 32 bytes")
        self._init()

    @property
    def audit_enabled(self) -> bool:
        return len(self._audit_secret) >= 32

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init(self):
        with closing(self._connect()) as conn, conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS case_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    change_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(tenant_id, change_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_case_versions_scope
                    ON case_versions(tenant_id, change_id, version DESC);

                CREATE TABLE IF NOT EXISTS analysis_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    change_id TEXT NOT NULL,
                    case_version INTEGER NOT NULL,
                    analysis_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_analysis_versions_scope
                    ON analysis_versions(tenant_id, change_id, id DESC);

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    change_id TEXT,
                    action TEXT NOT NULL,
                    detail_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE INDEX IF NOT EXISTS idx_audit_events_tenant
                    ON audit_events(tenant_id, id ASC);
                """
            )

    @staticmethod
    def _validate_scope(tenant_id: str, payload: dict[str, Any]):
        tenant_id = str(tenant_id or "").strip()
        payload_tenant = str(payload.get("tenant_id") or "").strip()
        if not tenant_id:
            raise ValueError("TENANT_REQUIRED")
        if not payload_tenant:
            raise ValueError("PAYLOAD_TENANT_REQUIRED")
        if payload_tenant != tenant_id:
            raise PermissionError("TENANT_MISMATCH")
        change_id = str(payload.get("change_id") or "").strip()
        if not change_id:
            raise ValueError("CHANGE_ID_REQUIRED")
        return tenant_id, change_id

    def _append_audit_conn(
        self,
        conn: sqlite3.Connection,
        tenant_id: str,
        change_id: str | None,
        action: str,
        detail: dict[str, Any],
    ) -> None:
        if not self.audit_enabled:
            return
        previous = conn.execute("SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1").fetchone()
        prev_hash = str(previous["event_hash"]) if previous else "GENESIS"
        created_at = _now()
        material = {
            "tenant_id": tenant_id,
            "change_id": change_id,
            "action": action,
            "detail": detail,
            "created_at": created_at,
            "prev_hash": prev_hash,
        }
        event_hash = hmac.new(self._audit_secret, _canonical(material).encode(), hashlib.sha256).hexdigest()
        conn.execute(
            """INSERT INTO audit_events
               (tenant_id, change_id, action, detail_json, created_at, prev_hash, event_hash)
               VALUES(?,?,?,?,?,?,?)""",
            (tenant_id, change_id, action, _canonical(detail), created_at, prev_hash, event_hash),
        )

    def verify_audit_chain(self) -> bool:
        if not self.audit_enabled:
            return False
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT * FROM audit_events ORDER BY id ASC").fetchall()
        prev_hash = "GENESIS"
        for row in rows:
            if row["prev_hash"] != prev_hash:
                return False
            try:
                detail = json.loads(row["detail_json"])
            except Exception:
                return False
            material = {
                "tenant_id": row["tenant_id"],
                "change_id": row["change_id"],
                "action": row["action"],
                "detail": detail,
                "created_at": row["created_at"],
                "prev_hash": row["prev_hash"],
            }
            expected = hmac.new(self._audit_secret, _canonical(material).encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(row["event_hash"], expected):
                return False
            prev_hash = row["event_hash"]
        return True

    def audit_history(self, tenant_id: str) -> list[dict[str, Any]]:
        tenant_id = str(tenant_id or "").strip()
        if not tenant_id:
            raise ValueError("TENANT_REQUIRED")
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT id, tenant_id, change_id, action, detail_json, created_at, prev_hash, event_hash FROM audit_events WHERE tenant_id=? ORDER BY id ASC",
                (tenant_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "tenant_id": row["tenant_id"],
                "change_id": row["change_id"],
                "action": row["action"],
                "detail": json.loads(row["detail_json"]),
                "created_at": row["created_at"],
                "prev_hash": row["prev_hash"],
                "event_hash": row["event_hash"],
            }
            for row in rows
        ]

    def save_case(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id, change_id = self._validate_scope(tenant_id, payload)
        encoded = _canonical(payload)
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM case_versions WHERE tenant_id=? AND change_id=?",
                (tenant_id, change_id),
            ).fetchone()
            version = int(row["v"]) + 1
            created_at = _now()
            conn.execute(
                "INSERT INTO case_versions(tenant_id, change_id, version, payload_json, created_at) VALUES(?,?,?,?,?)",
                (tenant_id, change_id, version, encoded, created_at),
            )
            self._append_audit_conn(conn, tenant_id, change_id, "CASE_VERSION_SAVED", {"version": version})
        return {"tenant_id": tenant_id, "change_id": change_id, "version": version, "created_at": created_at}

    def save_evaluated_case(self, tenant_id: str, payload: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
        tenant_id, change_id = self._validate_scope(tenant_id, payload)
        if str(analysis.get("tenant_id") or "").strip() != tenant_id or str(analysis.get("change_id") or "").strip() != change_id:
            raise ValueError("ANALYSIS_SCOPE_MISMATCH")
        payload_encoded = _canonical(payload)
        analysis_encoded = _canonical(analysis)
        created_at = _now()
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM case_versions WHERE tenant_id=? AND change_id=?",
                (tenant_id, change_id),
            ).fetchone()
            version = int(row["v"]) + 1
            conn.execute(
                "INSERT INTO case_versions(tenant_id, change_id, version, payload_json, created_at) VALUES(?,?,?,?,?)",
                (tenant_id, change_id, version, payload_encoded, created_at),
            )
            cur = conn.execute(
                "INSERT INTO analysis_versions(tenant_id, change_id, case_version, analysis_json, created_at) VALUES(?,?,?,?,?)",
                (tenant_id, change_id, version, analysis_encoded, created_at),
            )
            analysis_id = cur.lastrowid
            self._append_audit_conn(
                conn,
                tenant_id,
                change_id,
                "CASE_ANALYZED",
                {"case_version": version, "analysis_id": analysis_id},
            )
        return {
            "saved": {"tenant_id": tenant_id, "change_id": change_id, "version": version, "created_at": created_at},
            "analysis_saved": {"analysis_id": analysis_id, "tenant_id": tenant_id, "change_id": change_id, "case_version": version, "created_at": created_at},
        }

    def latest_case(self, tenant_id: str, change_id: str) -> dict[str, Any] | None:
        tenant_id = str(tenant_id or "").strip()
        change_id = str(change_id or "").strip()
        if not tenant_id:
            raise ValueError("TENANT_REQUIRED")
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM case_versions WHERE tenant_id=? AND change_id=? ORDER BY version DESC LIMIT 1",
                (tenant_id, change_id),
            ).fetchone()
        if not row:
            return None
        return {
            "tenant_id": row["tenant_id"],
            "change_id": row["change_id"],
            "version": row["version"],
            "created_at": row["created_at"],
            "payload": json.loads(row["payload_json"]),
        }

    def history(self, tenant_id: str, change_id: str) -> list[dict[str, Any]]:
        tenant_id = str(tenant_id or "").strip()
        change_id = str(change_id or "").strip()
        if not tenant_id:
            raise ValueError("TENANT_REQUIRED")
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM case_versions WHERE tenant_id=? AND change_id=? ORDER BY version ASC",
                (tenant_id, change_id),
            ).fetchall()
        return [
            {
                "tenant_id": row["tenant_id"],
                "change_id": row["change_id"],
                "version": row["version"],
                "created_at": row["created_at"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def save_analysis(self, tenant_id: str, change_id: str, case_version: int, analysis: dict[str, Any]) -> dict[str, Any]:
        tenant_id = str(tenant_id or "").strip()
        change_id = str(change_id or "").strip()
        if not tenant_id:
            raise ValueError("TENANT_REQUIRED")
        encoded = _canonical(analysis)
        created_at = _now()
        with closing(self._connect()) as conn, conn:
            exists = conn.execute(
                "SELECT 1 FROM case_versions WHERE tenant_id=? AND change_id=? AND version=?",
                (tenant_id, change_id, int(case_version)),
            ).fetchone()
            if not exists:
                raise ValueError("CASE_VERSION_NOT_FOUND")
            cur = conn.execute(
                "INSERT INTO analysis_versions(tenant_id, change_id, case_version, analysis_json, created_at) VALUES(?,?,?,?,?)",
                (tenant_id, change_id, int(case_version), encoded, created_at),
            )
            analysis_id = cur.lastrowid
            self._append_audit_conn(conn, tenant_id, change_id, "ANALYSIS_SAVED", {"case_version": int(case_version), "analysis_id": analysis_id})
        return {"analysis_id": analysis_id, "tenant_id": tenant_id, "change_id": change_id, "case_version": int(case_version), "created_at": created_at}

    def integrity_check(self) -> bool:
        with closing(self._connect()) as conn:
            row = conn.execute("PRAGMA integrity_check").fetchone()
        return bool(row and row[0] == "ok")

    def backup_to(self, destination: str | Path) -> str:
        """Development-only plaintext SQLite backup. Production uses backup_encrypted_to."""
        destination = str(destination)
        with closing(self._connect()) as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
        return destination

    def restore_from(self, source_path: str | Path) -> None:
        """Development-only plaintext restore. Production uses restore_encrypted_from."""
        source_path = str(source_path)
        with closing(sqlite3.connect(source_path)) as source:
            check = source.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                raise ValueError("BACKUP_INTEGRITY_FAILED")
            with closing(self._connect()) as target:
                source.backup(target)
        if not self.integrity_check():
            raise ValueError("RESTORE_INTEGRITY_FAILED")

    def backup_encrypted_to(self, destination: str | Path, *, key: bytes) -> str:
        if len(key) != 32:
            raise ValueError("AES256_KEY_REQUIRED")
        destination = Path(destination)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            plain_path = Path(tmp.name)
        try:
            self.backup_to(plain_path)
            plain = plain_path.read_bytes()
            nonce = os.urandom(12)
            ciphertext = AESGCM(key).encrypt(nonce, plain, BACKUP_MAGIC)
            temp_destination = destination.with_suffix(destination.suffix + ".tmp")
            temp_destination.write_bytes(BACKUP_MAGIC + nonce + ciphertext)
            temp_destination.replace(destination)
        finally:
            plain_path.unlink(missing_ok=True)
        return str(destination)

    def restore_encrypted_from(self, source_path: str | Path, *, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("AES256_KEY_REQUIRED")
        blob = Path(source_path).read_bytes()
        if len(blob) <= len(BACKUP_MAGIC) + 12 or not blob.startswith(BACKUP_MAGIC):
            raise ValueError("INVALID_ENCRYPTED_BACKUP")
        nonce_start = len(BACKUP_MAGIC)
        nonce = blob[nonce_start:nonce_start + 12]
        ciphertext = blob[nonce_start + 12:]
        try:
            plain = AESGCM(key).decrypt(nonce, ciphertext, BACKUP_MAGIC)
        except Exception as exc:
            raise ValueError("BACKUP_DECRYPTION_FAILED") from exc
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            plain_path = Path(tmp.name)
            tmp.write(plain)
        try:
            self.restore_from(plain_path)
        finally:
            plain_path.unlink(missing_ok=True)
        if self.audit_enabled:
            if not self.verify_audit_chain():
                raise ValueError("RESTORED_AUDIT_CHAIN_FAILED")
            with closing(self._connect()) as conn, conn:
                self._append_audit_conn(conn, "SYSTEM", None, "ENCRYPTED_BACKUP_RESTORED", {})

    def purge_change(self, tenant_id: str, change_id: str, *, actor_role: str) -> dict[str, int]:
        tenant_id = str(tenant_id or "").strip()
        change_id = str(change_id or "").strip()
        if not tenant_id or not change_id:
            raise ValueError("TENANT_AND_CHANGE_REQUIRED")
        if str(actor_role or "").upper() != "OWNER":
            raise PermissionError("OWNER_REQUIRED")
        if not self.audit_enabled:
            raise RuntimeError("AUDIT_REQUIRED_FOR_PURGE")
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            analyses = conn.execute(
                "DELETE FROM analysis_versions WHERE tenant_id=? AND change_id=?",
                (tenant_id, change_id),
            ).rowcount
            cases = conn.execute(
                "DELETE FROM case_versions WHERE tenant_id=? AND change_id=?",
                (tenant_id, change_id),
            ).rowcount
            self._append_audit_conn(conn, tenant_id, change_id, "CASE_PURGED", {"case_versions": cases, "analysis_versions": analyses})
        return {"case_versions": cases, "analysis_versions": analyses}

    def purge_before(self, tenant_id: str, before_iso: str, *, actor_role: str) -> dict[str, int]:
        tenant_id = str(tenant_id or "").strip()
        if not tenant_id:
            raise ValueError("TENANT_REQUIRED")
        if str(actor_role or "").upper() != "OWNER":
            raise PermissionError("OWNER_REQUIRED")
        if not self.audit_enabled:
            raise RuntimeError("AUDIT_REQUIRED_FOR_PURGE")
        datetime.fromisoformat(str(before_iso).replace("Z", "+00:00"))
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """SELECT change_id FROM case_versions WHERE tenant_id=?
                   GROUP BY change_id HAVING MAX(created_at) < ?""",
                (tenant_id, before_iso),
            ).fetchall()
            ids = [str(row["change_id"]) for row in rows]
            cases = analyses = 0
            for change_id in ids:
                analyses += conn.execute("DELETE FROM analysis_versions WHERE tenant_id=? AND change_id=?", (tenant_id, change_id)).rowcount
                cases += conn.execute("DELETE FROM case_versions WHERE tenant_id=? AND change_id=?", (tenant_id, change_id)).rowcount
            self._append_audit_conn(conn, tenant_id, None, "RETENTION_PURGE", {"changes": len(ids), "case_versions": cases, "analysis_versions": analyses, "before": before_iso})
        return {"changes": len(ids), "case_versions": cases, "analysis_versions": analyses}

    def analysis_history(self, tenant_id: str, change_id: str) -> list[dict[str, Any]]:
        tenant_id = str(tenant_id or "").strip()
        if not tenant_id:
            raise ValueError("TENANT_REQUIRED")
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM analysis_versions WHERE tenant_id=? AND change_id=? ORDER BY id ASC",
                (tenant_id, change_id),
            ).fetchall()
        return [
            {
                "analysis_id": row["id"],
                "tenant_id": row["tenant_id"],
                "change_id": row["change_id"],
                "case_version": row["case_version"],
                "created_at": row["created_at"],
                "analysis": json.loads(row["analysis_json"]),
            }
            for row in rows
        ]
