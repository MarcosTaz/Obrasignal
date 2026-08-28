from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CaseStore:
    """Tenant-scoped append-only case and analysis history.

    This is an MVP persistence boundary, not a production authentication layer.
    Every operation requires an explicit tenant id and queries are scoped by it.
    """

    def __init__(self, path: str | Path):
        self.path = str(path)
        self._init()

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.row_factory = sqlite3.Row
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

    def save_case(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id, change_id = self._validate_scope(tenant_id, payload)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
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
        return {"tenant_id": tenant_id, "change_id": change_id, "version": version, "created_at": created_at}

    def save_evaluated_case(self, tenant_id: str, payload: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
        tenant_id, change_id = self._validate_scope(tenant_id, payload)
        if str(analysis.get("tenant_id") or "").strip() != tenant_id or str(analysis.get("change_id") or "").strip() != change_id:
            raise ValueError("ANALYSIS_SCOPE_MISMATCH")
        payload_encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        analysis_encoded = json.dumps(analysis, sort_keys=True, separators=(",", ":"))
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
        return {
            "saved": {"tenant_id": tenant_id, "change_id": change_id, "version": version, "created_at": created_at},
            "analysis_saved": {"analysis_id": analysis_id, "tenant_id": tenant_id, "change_id": change_id, "case_version": version, "created_at": created_at},
        }

    def latest_case(self, tenant_id: str, change_id: str) -> dict[str, Any] | None:
        tenant_id = str(tenant_id or "").strip()
        change_id = str(change_id or "").strip()
        if not tenant_id:
            raise ValueError("TENANT_REQUIRED")
        with closing(self._connect()) as conn, conn:
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
        with closing(self._connect()) as conn, conn:
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
        encoded = json.dumps(analysis, sort_keys=True, separators=(",", ":"))
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
        return {"analysis_id": analysis_id, "tenant_id": tenant_id, "change_id": change_id, "case_version": int(case_version), "created_at": created_at}

    def integrity_check(self) -> bool:
        with closing(self._connect()) as conn, conn:
            row = conn.execute("PRAGMA integrity_check").fetchone()
        return bool(row and row[0] == "ok")

    def backup_to(self, destination: str | Path) -> str:
        destination = str(destination)
        with closing(self._connect()) as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
        return destination

    def restore_from(self, source_path: str | Path) -> None:
        source_path = str(source_path)
        with closing(sqlite3.connect(source_path)) as source:
            check = source.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                raise ValueError("BACKUP_INTEGRITY_FAILED")
            with closing(self._connect()) as target:
                source.backup(target)
        if not self.integrity_check():
            raise ValueError("RESTORE_INTEGRITY_FAILED")

    def analysis_history(self, tenant_id: str, change_id: str) -> list[dict[str, Any]]:
        tenant_id = str(tenant_id or "").strip()
        if not tenant_id:
            raise ValueError("TENANT_REQUIRED")
        with closing(self._connect()) as conn, conn:
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
