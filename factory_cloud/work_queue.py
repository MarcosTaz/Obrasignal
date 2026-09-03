from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from factory_cloud.adapters import ExecutionRequest, ExecutionResult
from factory_cloud.state_store import StateStore, StateStoreError, utc_now

JOB_TERMINAL = {"DONE", "WAIT", "BLOCKED", "ERROR"}
APP_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class QueueStore:
    """Queue-only SQLite store suitable for one physically isolated app queue."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            yield conn
        finally:
            conn.close()


def app_queue_path(queue_dir: str | Path, app_id: str) -> Path:
    if not APP_ID_RE.fullmatch(app_id or ""):
        raise StateStoreError("safe app_id required for queue path")
    return Path(queue_dir) / app_id / "queue.sqlite3"


def open_app_queue(queue_dir: str | Path, app_id: str) -> "DurableWorkQueue":
    return DurableWorkQueue(QueueStore(app_queue_path(queue_dir, app_id)), app_id_scope=app_id)


class DurableWorkQueue:
    """Metadata-only handoff queue between control plane and app-specific workers.

    Runtime workers should use a queue-only SQLite file scoped to exactly one app.
    The legacy StateStore-backed form remains available for in-process tests and
    migrations, but it is not an isolation boundary between app worker processes.
    """

    def __init__(self, store: StateStore | QueueStore, app_id_scope: str | None = None):
        if app_id_scope is not None and not APP_ID_RE.fullmatch(app_id_scope):
            raise StateStoreError("safe app_id_scope required")
        self.store = store
        self.app_id_scope = app_id_scope
        with self.store.connection() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS worker_jobs (
                    job_id TEXT PRIMARY KEY,
                    app_id TEXT NOT NULL,
                    task TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    claimed_by TEXT,
                    claim_expires_at TEXT,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT,
                    consumed_at TEXT
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_worker_jobs_app_status ON worker_jobs(app_id,status,created_at)")
            conn.commit()

    def _require_scope(self, app_id: str) -> None:
        if self.app_id_scope is not None and app_id != self.app_id_scope:
            raise StateStoreError(f"cross-app queue access rejected: {app_id}")

    def _require_job_scope(self, conn: sqlite3.Connection, job_id: str) -> sqlite3.Row | None:
        row = conn.execute("SELECT * FROM worker_jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is not None:
            self._require_scope(row["app_id"])
        return row

    @staticmethod
    def _decode(row) -> dict[str, Any]:
        item = dict(row)
        item["request"] = json.loads(item.pop("request_json"))
        raw = item.pop("result_json")
        item["result"] = json.loads(raw) if raw else None
        return item

    def submit_or_get(self, request: ExecutionRequest) -> dict[str, Any]:
        self._require_scope(request.app_id)
        now = utc_now()
        with self.store.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """SELECT * FROM worker_jobs
                   WHERE app_id=? AND task=? AND consumed_at IS NULL
                   ORDER BY created_at DESC LIMIT 1""",
                (request.app_id, request.task),
            ).fetchone()
            if row is None:
                job_id = uuid.uuid4().hex
                conn.execute(
                    """INSERT INTO worker_jobs(job_id,app_id,task,request_json,status,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?)""",
                    (job_id, request.app_id, request.task, json.dumps(asdict(request), sort_keys=True), "QUEUED", now, now),
                )
                row = conn.execute("SELECT * FROM worker_jobs WHERE job_id=?", (job_id,)).fetchone()
            conn.commit()
        return self._decode(row)

    def claim(self, app_id: str, worker_id: str, lease_seconds: float = 60.0) -> dict[str, Any] | None:
        self._require_scope(app_id)
        if lease_seconds <= 0:
            raise StateStoreError("positive worker job lease required")
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        expires = (now_dt + timedelta(seconds=lease_seconds)).isoformat()
        with self.store.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """SELECT * FROM worker_jobs WHERE app_id=? AND consumed_at IS NULL
                   AND status IN ('QUEUED','RUNNING') ORDER BY created_at ASC""",
                (app_id,),
            ).fetchall()
            chosen = None
            for row in rows:
                if row["status"] == "QUEUED":
                    chosen = row
                    break
                raw_expiry = row["claim_expires_at"]
                try:
                    expired = not raw_expiry or datetime.fromisoformat(raw_expiry) <= now_dt
                except ValueError:
                    expired = False
                if expired:
                    chosen = row
                    break
            if chosen is None:
                conn.commit()
                return None
            conn.execute(
                """UPDATE worker_jobs SET status='RUNNING', claimed_by=?, claim_expires_at=?,
                   attempt=attempt+1, updated_at=? WHERE job_id=?""",
                (worker_id, expires, now, chosen["job_id"]),
            )
            row = conn.execute("SELECT * FROM worker_jobs WHERE job_id=?", (chosen["job_id"],)).fetchone()
            conn.commit()
        return self._decode(row)

    def renew_claim(self, job_id: str, worker_id: str, lease_seconds: float) -> bool:
        expires = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()
        with self.store.connection() as conn:
            self._require_job_scope(conn, job_id)
            cur = conn.execute(
                """UPDATE worker_jobs SET claim_expires_at=?, updated_at=?
                   WHERE job_id=? AND claimed_by=? AND status='RUNNING'""",
                (expires, utc_now(), job_id, worker_id),
            )
            conn.commit()
            return cur.rowcount == 1

    def finish(self, job_id: str, worker_id: str, result: ExecutionResult) -> None:
        if result.status not in JOB_TERMINAL:
            raise StateStoreError(f"invalid worker result status: {result.status}")
        now = utc_now()
        with self.store.connection() as conn:
            self._require_job_scope(conn, job_id)
            cur = conn.execute(
                """UPDATE worker_jobs SET status=?, result_json=?, finished_at=?, updated_at=?, claim_expires_at=NULL
                   WHERE job_id=? AND claimed_by=? AND status='RUNNING'""",
                (result.status, json.dumps(asdict(result), sort_keys=True), now, now, job_id, worker_id),
            )
            if cur.rowcount != 1:
                raise StateStoreError(f"worker job claim lost: {job_id}")
            conn.commit()

    def consume(self, job_id: str) -> dict[str, Any]:
        now = utc_now()
        with self.store.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._require_job_scope(conn, job_id)
            if row is None or row["status"] not in JOB_TERMINAL or row["consumed_at"] is not None:
                conn.rollback()
                raise StateStoreError(f"worker result not consumable: {job_id}")
            conn.execute("UPDATE worker_jobs SET consumed_at=?, updated_at=? WHERE job_id=?", (now, now, job_id))
            conn.commit()
        return self._decode(row)

    def jobs(self, app_id: str | None = None) -> list[dict[str, Any]]:
        if self.app_id_scope is not None:
            if app_id is None:
                app_id = self.app_id_scope
            self._require_scope(app_id)
        with self.store.connection() as conn:
            if app_id:
                rows = conn.execute("SELECT * FROM worker_jobs WHERE app_id=? ORDER BY created_at", (app_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM worker_jobs ORDER BY created_at").fetchall()
        return [self._decode(row) for row in rows]


class QueuedAppAdapter:
    """Control-plane adapter that delegates work without sharing app credentials."""

    def __init__(self, queue: DurableWorkQueue):
        self.queue = queue

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        job = self.queue.submit_or_get(request)
        if job["status"] in {"QUEUED", "RUNNING"}:
            return ExecutionResult(
                status="WAIT",
                evidence={"worker_job_id": job["job_id"], "worker_job_status": job["status"]},
                next_active=request.task,
                blockers=("app_worker_execution_pending",),
                resume_at=request.task,
            )
        completed = self.queue.consume(job["job_id"])
        result = completed["result"] or {}
        return ExecutionResult(
            status=result.get("status", "ERROR"), evidence=result.get("evidence") or {},
            next_active=result.get("next_active") or "", next_items=tuple(result.get("next_items") or ()),
            wait_items=tuple(result.get("wait_items") or ()), blockers=tuple(result.get("blockers") or ()),
            resume_at=result.get("resume_at") or request.task,
            last_verified=result.get("last_verified"), last_green=result.get("last_green"),
            execution_branch=result.get("execution_branch"), execution_head=result.get("execution_head"),
            error=result.get("error"),
        )
