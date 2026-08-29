from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .engine import ENGINE_VERSION, evaluate_recoverability
from .identifiers import CASE_ID_ADDRESSABILITY_ERROR, is_addressable_case_id
from .state import AssistedCaseState, dump_state, load_state


class CapacityRepository:
    """Small tenant-scoped SQLite repository for assisted T1 cases.

    It stores checksummed source-state envelopes together with the engine
    version that accepted them. Derived recoverability/package outputs are
    recomputed only when the stored engine version matches the running engine;
    semantic version drift fails closed and requires explicit reassessment.

    T1 treats save as create-only. An exact retry of the same tenant/case
    snapshot is idempotent; a different snapshot for the same identity is a
    conflict and never an implicit overwrite.
    """

    def __init__(self, db_path: str):
        if not db_path or db_path == ":memory:":
            raise ValueError("db_path must be a durable filesystem path")
        self.db_path = str(Path(db_path))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @staticmethod
    def _validate_case_id(case_id) -> str:
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError("case_id must be a non-empty string")
        if not is_addressable_case_id(case_id):
            raise ValueError(CASE_ID_ADDRESSABILITY_ERROR)
        return case_id

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS capacity_commitment_cases (
                    tenant_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    snapshot TEXT NOT NULL,
                    engine_version TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, case_id)
                )
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(capacity_commitment_cases)").fetchall()
            }
            required = {"tenant_id", "case_id", "snapshot", "engine_version", "updated_at"}
            if not required.issubset(columns):
                raise RuntimeError("capacity repository schema requires explicit migration")

    def save(self, state: AssistedCaseState) -> bool:
        """Create validated state, returning True if inserted and False for exact retry."""

        case_id = self._validate_case_id(state.recovery_case.case_id)
        evaluate_recoverability(state.recovery_case)
        snapshot = dump_state(state)
        updated_at = datetime.now(timezone.utc).isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO capacity_commitment_cases
                        (tenant_id, case_id, snapshot, engine_version, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (state.tenant_id, case_id, snapshot, ENGINE_VERSION, updated_at),
                )
            return True
        except sqlite3.IntegrityError as exc:
            with self._connect() as conn:
                existing = conn.execute(
                    """
                    SELECT snapshot, engine_version FROM capacity_commitment_cases
                    WHERE tenant_id=? AND case_id=?
                    """,
                    (state.tenant_id, case_id),
                ).fetchone()
            if existing is None:
                raise FileExistsError("case already exists") from exc
            if existing["engine_version"] != ENGINE_VERSION:
                raise RuntimeError("case requires explicit reassessment for engine version drift") from exc
            if existing["snapshot"] == snapshot:
                return False
            raise FileExistsError("case already exists with different source state") from exc

    def load(self, *, tenant_id: str, case_id: str) -> AssistedCaseState:
        if not tenant_id:
            raise ValueError("tenant_id and case_id are required")
        self._validate_case_id(case_id)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT snapshot, engine_version FROM capacity_commitment_cases
                WHERE tenant_id=? AND case_id=?
                """,
                (tenant_id, case_id),
            ).fetchone()
        if row is None:
            raise KeyError("case not found")
        if row["engine_version"] != ENGINE_VERSION:
            raise RuntimeError("case requires explicit reassessment for engine version drift")
        state = load_state(row["snapshot"], expected_tenant_id=tenant_id)
        if state.recovery_case.case_id != case_id:
            raise RuntimeError("capacity repository case identity mismatch")
        evaluate_recoverability(state.recovery_case)
        return state

    def list_case_ids(self, *, tenant_id: str) -> List[str]:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT case_id FROM capacity_commitment_cases
                WHERE tenant_id=? ORDER BY case_id
                """,
                (tenant_id,),
            ).fetchall()
        case_ids = [row["case_id"] for row in rows]
        for case_id in case_ids:
            try:
                self._validate_case_id(case_id)
            except ValueError as exc:
                raise RuntimeError("capacity repository case identity mismatch") from exc
        return case_ids

    def backup_to(self, destination_path: str) -> None:
        if not destination_path:
            raise ValueError("destination_path is required")
        destination = str(Path(destination_path))
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        if os.path.abspath(destination) == os.path.abspath(self.db_path):
            raise ValueError("backup destination must differ from source")
        with self._connect() as source, sqlite3.connect(destination) as dest:
            source.backup(dest)

    def restore_from(self, source_path: str) -> None:
        """Restore only after fully validating the backup snapshots/version."""

        if not source_path or not Path(source_path).is_file():
            raise ValueError("restore source does not exist")
        if os.path.abspath(source_path) == os.path.abspath(self.db_path):
            raise ValueError("restore source must differ from destination")

        source = sqlite3.connect(source_path)
        source.row_factory = sqlite3.Row
        try:
            table = source.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='capacity_commitment_cases'
                """
            ).fetchone()
            if table is None:
                raise ValueError("restore source lacks capacity schema")
            columns = {
                row["name"]
                for row in source.execute("PRAGMA table_info(capacity_commitment_cases)").fetchall()
            }
            required = {"tenant_id", "case_id", "snapshot", "engine_version", "updated_at"}
            if not required.issubset(columns):
                raise ValueError("restore source lacks required capacity columns")
            rows = source.execute(
                "SELECT tenant_id, case_id, snapshot, engine_version FROM capacity_commitment_cases"
            ).fetchall()
            for row in rows:
                try:
                    self._validate_case_id(row["case_id"])
                except ValueError as exc:
                    raise ValueError("restore source has invalid case identity") from exc
                if row["engine_version"] != ENGINE_VERSION:
                    raise ValueError("restore source requires explicit engine reassessment")
                state = load_state(row["snapshot"], expected_tenant_id=row["tenant_id"])
                if state.recovery_case.case_id != row["case_id"]:
                    raise ValueError("restore source case identity mismatch")
                evaluate_recoverability(state.recovery_case)

            with self._connect() as destination:
                source.backup(destination)
        finally:
            source.close()
