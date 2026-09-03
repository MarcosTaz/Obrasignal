from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

STATE_SCHEMA_VERSION = 3


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStoreError(RuntimeError):
    pass


class StateStore:
    """Durable orchestration metadata; never app production authority or secrets."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, name: str, declaration: str) -> None:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if name in columns:
            return
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")
        except sqlite3.OperationalError as exc:
            # Concurrent process startup may race between PRAGMA and ALTER. Only a
            # duplicate-column outcome is safe to accept; everything else remains fatal.
            if "duplicate column" not in str(exc).lower():
                raise

    def _initialize(self) -> None:
        with self.connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS factory_cloud_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS app_state (
                    app_id TEXT PRIMARY KEY, mission TEXT NOT NULL DEFAULT '', repo_source TEXT,
                    canonical_head TEXT, execution_branch TEXT, execution_head TEXT,
                    runtime TEXT, state TEXT NOT NULL, active TEXT NOT NULL DEFAULT '',
                    next_json TEXT NOT NULL DEFAULT '[]', wait_json TEXT NOT NULL DEFAULT '[]',
                    blockers_json TEXT NOT NULL DEFAULT '[]', last_verified TEXT, last_green TEXT,
                    priority INTEGER NOT NULL DEFAULT 0, resume_at TEXT NOT NULL DEFAULT '',
                    current_execution_json TEXT, error_state_json TEXT,
                    retry_state_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL
                )"""
            )
            self._ensure_column(conn, "app_state", "execution_branch", "TEXT")
            self._ensure_column(conn, "app_state", "execution_head", "TEXT")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS execution_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, app_id TEXT NOT NULL, execution_id TEXT NOT NULL,
                    status TEXT NOT NULL, task TEXT NOT NULL, evidence_json TEXT NOT NULL DEFAULT '{}',
                    error_json TEXT, started_at TEXT NOT NULL, finished_at TEXT,
                    FOREIGN KEY(app_id) REFERENCES app_state(app_id) ON DELETE CASCADE
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_history_app ON execution_history(app_id, id DESC)")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS orchestrator_lease (
                    lease_name TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
                    acquired_at TEXT NOT NULL, expires_at TEXT NOT NULL
                )"""
            )
            conn.execute("INSERT OR REPLACE INTO factory_cloud_meta(key,value) VALUES('schema_version',?)", (str(STATE_SCHEMA_VERSION),))
            conn.commit()

    def acquire_or_renew_lease(self, lease_name: str, owner_id: str, ttl_seconds: float = 30.0) -> bool:
        if not lease_name or not owner_id or ttl_seconds <= 0:
            raise StateStoreError("lease_name, owner_id and positive ttl are required")
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        expires = (now_dt + timedelta(seconds=ttl_seconds)).isoformat()
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT owner_id, expires_at FROM orchestrator_lease WHERE lease_name=?", (lease_name,)).fetchone()
            can_claim = row is None or row["owner_id"] == owner_id
            if row is not None and not can_claim:
                try:
                    can_claim = datetime.fromisoformat(row["expires_at"]) <= now_dt
                except ValueError:
                    can_claim = False
            if can_claim:
                conn.execute(
                    """INSERT INTO orchestrator_lease(lease_name,owner_id,acquired_at,expires_at)
                       VALUES(?,?,?,?) ON CONFLICT(lease_name) DO UPDATE SET
                       owner_id=excluded.owner_id, acquired_at=excluded.acquired_at, expires_at=excluded.expires_at""",
                    (lease_name, owner_id, now, expires),
                )
            conn.commit()
        return can_claim

    def release_lease(self, lease_name: str, owner_id: str) -> bool:
        with self.connection() as conn:
            cur = conn.execute("DELETE FROM orchestrator_lease WHERE lease_name=? AND owner_id=?", (lease_name, owner_id))
            conn.commit()
            return cur.rowcount == 1

    def lease(self, lease_name: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM orchestrator_lease WHERE lease_name=?", (lease_name,)).fetchone()
        return dict(row) if row else None

    def upsert_from_registry(self, app: dict[str, Any]) -> None:
        source = app.get("source_truth") or {}
        execution = app.get("execution_source") or {}
        activation = app.get("activation") or {}
        baton = app.get("baton") or {}
        repo_source = source.get("repository") or source.get("canonical_repository") or source.get("project")
        canonical_head = source.get("canonical_head")
        execution_branch = str(execution.get("branch") or "").strip() or None
        execution_head = str(execution.get("head") or "").strip() or None
        runtime = source.get("provider")
        now = utc_now()
        with self.connection() as conn:
            existing = conn.execute("SELECT app_id FROM app_state WHERE app_id=?", (app["app_id"],)).fetchone()
            if existing:
                conn.execute(
                    """UPDATE app_state SET repo_source=?, canonical_head=?,
                       execution_branch=COALESCE(execution_branch, ?),
                       execution_head=COALESCE(execution_head, ?),
                       runtime=?, priority=?, updated_at=? WHERE app_id=?""",
                    (
                        repo_source, canonical_head, execution_branch, execution_head, runtime,
                        int(activation.get("priority", 0)), now, app["app_id"],
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO app_state(app_id,mission,repo_source,canonical_head,execution_branch,execution_head,
                    runtime,state,active,next_json,wait_json,blockers_json,last_verified,last_green,priority,resume_at,
                    current_execution_json,error_state_json,retry_state_json,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        app["app_id"], app.get("mission", ""), repo_source, canonical_head,
                        execution_branch, execution_head, runtime, app.get("development_state", "UNKNOWN"),
                        str(baton.get("active") or ""), json.dumps(baton.get("next", [])),
                        json.dumps(baton.get("wait", [])), "[]",
                        now if source.get("verified") or source.get("verified_runtime") else None,
                        execution_head or (canonical_head if source.get("verified") else None),
                        int(activation.get("priority", 0)), str(baton.get("active") or ""),
                        None, None, "{}", now,
                    ),
                )
            conn.commit()

    def get_app(self, app_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM app_state WHERE app_id=?", (app_id,)).fetchone()
        return self._decode(row) if row else None

    def list_apps(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM app_state ORDER BY priority DESC, app_id ASC").fetchall()
        return [self._decode(row) for row in rows]

    def checkpoint(self, app_id: str, **changes: Any) -> None:
        allowed = {
            "mission", "canonical_head", "execution_branch", "execution_head", "state", "active",
            "last_verified", "last_green", "priority", "resume_at", "current_execution_json",
            "error_state_json", "retry_state_json", "next_json", "wait_json", "blockers_json",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise StateStoreError(f"unsupported checkpoint fields: {sorted(unknown)}")
        encoded = dict(changes)
        for key in ("next_json", "wait_json", "blockers_json", "current_execution_json", "error_state_json", "retry_state_json"):
            if key in encoded and encoded[key] is not None and not isinstance(encoded[key], str):
                encoded[key] = json.dumps(encoded[key], sort_keys=True)
        encoded["updated_at"] = utc_now()
        assignments = ", ".join(f"{key}=?" for key in encoded)
        with self.connection() as conn:
            cur = conn.execute(f"UPDATE app_state SET {assignments} WHERE app_id=?", list(encoded.values()) + [app_id])
            if cur.rowcount != 1:
                raise StateStoreError(f"unknown app_id: {app_id}")
            conn.commit()

    def start_execution(self, app_id: str, execution_id: str, task: str, payload: dict[str, Any]) -> None:
        now = utc_now()
        with self.connection() as conn:
            conn.execute("INSERT INTO execution_history(app_id,execution_id,status,task,evidence_json,started_at) VALUES(?,?,?,?,?,?)",
                         (app_id, execution_id, "EXECUTING", task, "{}", now))
            conn.execute("UPDATE app_state SET state='EXECUTING', current_execution_json=?, resume_at=?, updated_at=? WHERE app_id=?",
                         (json.dumps(payload, sort_keys=True), task, now, app_id))
            conn.commit()

    def finish_execution(self, app_id: str, execution_id: str, status: str, evidence: dict[str, Any], error: dict[str, Any] | None = None) -> None:
        now = utc_now()
        with self.connection() as conn:
            cur = conn.execute(
                "UPDATE execution_history SET status=?, evidence_json=?, error_json=?, finished_at=? WHERE app_id=? AND execution_id=? AND finished_at IS NULL",
                (status, json.dumps(evidence, sort_keys=True), json.dumps(error, sort_keys=True) if error else None, now, app_id, execution_id),
            )
            if cur.rowcount != 1:
                raise StateStoreError(f"active execution not found: {app_id}/{execution_id}")
            conn.commit()

    def history(self, app_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM execution_history WHERE app_id=? ORDER BY id DESC LIMIT ?", (app_id, limit)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            for key in ("evidence_json", "error_json"):
                item[key[:-5]] = json.loads(item.pop(key)) if item[key] else None
            result.append(item)
        return result

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        for key in ("next_json", "wait_json", "blockers_json", "current_execution_json", "error_state_json", "retry_state_json"):
            value = item.pop(key)
            item[key[:-5]] = json.loads(value) if value else None
        return item
