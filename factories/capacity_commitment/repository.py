from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .engine import ENGINE_VERSION, evaluate_recoverability
from .identifiers import CASE_ID_ADDRESSABILITY_ERROR, is_addressable_case_id
from .state import AssistedCaseState, dump_state, load_state


_SCHEMA_COLUMNS = {"tenant_id", "case_id", "snapshot", "engine_version", "updated_at"}
_PRIMARY_KEY = ("tenant_id", "case_id")
_TABLE_NAME = "capacity_commitment_cases"
_LINEAGE_SCHEMA_COLUMNS = {"tenant_id", "child_case_id", "parent_case_id", "created_at"}
_LINEAGE_PRIMARY_KEY = ("tenant_id", "child_case_id")
_LINEAGE_TABLE_NAME = "capacity_commitment_case_revisions"


def _same_physical_file(first: str, second: str) -> bool:
    if os.path.abspath(first) == os.path.abspath(second):
        return True
    try:
        return os.path.samefile(first, second)
    except (FileNotFoundError, OSError):
        return False


class CapacityRepository:
    """Tenant-scoped SQLite repository for immutable assisted cases.

    Source-state snapshots are create-only and checksummed. A changed contract,
    amendment, actuals correction, or evidence update is represented as a new
    immutable case revision linked to its parent; the prior snapshot is never
    overwritten. Exact retries remain idempotent.
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

    @staticmethod
    def _schema_error(conn: sqlite3.Connection) -> str | None:
        rows = conn.execute(f"PRAGMA table_info({_TABLE_NAME})").fetchall()
        if not rows:
            return "capacity schema is missing"
        names = {row["name"] for row in rows}
        missing = _SCHEMA_COLUMNS - names
        if missing:
            return "lacks required capacity columns"
        extra = names - _SCHEMA_COLUMNS
        if extra:
            return "capacity schema has unknown columns and requires explicit migration"
        primary_key = tuple(
            row["name"] for row in sorted((row for row in rows if row["pk"]), key=lambda row: row["pk"])
        )
        if primary_key != _PRIMARY_KEY:
            return "capacity schema primary key must be (tenant_id, case_id)"
        for row in rows:
            if str(row["type"] or "").upper() != "TEXT":
                return "capacity schema columns must use TEXT storage"
            if row["notnull"] != 1:
                return "capacity schema columns must be NOT NULL"

        triggers = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=?",
            (_TABLE_NAME,),
        ).fetchall()
        if triggers:
            return "capacity schema contains unexpected trigger"

        custom_indexes = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name=? AND sql IS NOT NULL
            """,
            (_TABLE_NAME,),
        ).fetchall()
        if custom_indexes:
            return "capacity schema contains unexpected index"

        foreign_keys = conn.execute(f"PRAGMA foreign_key_list({_TABLE_NAME})").fetchall()
        if foreign_keys:
            return "capacity schema contains unexpected foreign key"
        return None

    @staticmethod
    def _lineage_schema_error(conn: sqlite3.Connection) -> str | None:
        rows = conn.execute(f"PRAGMA table_info({_LINEAGE_TABLE_NAME})").fetchall()
        if not rows:
            return "capacity revision lineage schema is missing"
        names = {row["name"] for row in rows}
        missing = _LINEAGE_SCHEMA_COLUMNS - names
        if missing:
            return "revision lineage schema lacks required columns"
        extra = names - _LINEAGE_SCHEMA_COLUMNS
        if extra:
            return "revision lineage schema has unknown columns and requires explicit migration"
        primary_key = tuple(
            row["name"] for row in sorted((row for row in rows if row["pk"]), key=lambda row: row["pk"])
        )
        if primary_key != _LINEAGE_PRIMARY_KEY:
            return "revision lineage primary key must be (tenant_id, child_case_id)"
        for row in rows:
            if str(row["type"] or "").upper() != "TEXT":
                return "revision lineage columns must use TEXT storage"
            if row["notnull"] != 1:
                return "revision lineage columns must be NOT NULL"
        triggers = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=?",
            (_LINEAGE_TABLE_NAME,),
        ).fetchall()
        if triggers:
            return "revision lineage schema contains unexpected trigger"
        custom_indexes = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name=? AND sql IS NOT NULL
            """,
            (_LINEAGE_TABLE_NAME,),
        ).fetchall()
        if custom_indexes:
            return "revision lineage schema contains unexpected index"
        foreign_keys = conn.execute(f"PRAGMA foreign_key_list({_LINEAGE_TABLE_NAME})").fetchall()
        if foreign_keys:
            return "revision lineage schema contains unexpected foreign key"
        return None

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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS capacity_commitment_case_revisions (
                    tenant_id TEXT NOT NULL,
                    child_case_id TEXT NOT NULL,
                    parent_case_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, child_case_id)
                )
                """
            )
            schema_error = self._schema_error(conn)
            if schema_error:
                raise RuntimeError(f"{schema_error}; explicit migration required")
            lineage_error = self._lineage_schema_error(conn)
            if lineage_error:
                raise RuntimeError(f"{lineage_error}; explicit migration required")

    def _load_validated_row(
        self,
        conn: sqlite3.Connection,
        *,
        tenant_id: str,
        case_id: str,
    ) -> AssistedCaseState:
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

    def _validated_lineage_chain(
        self,
        conn: sqlite3.Connection,
        *,
        tenant_id: str,
        case_id: str,
    ) -> List[str]:
        self._load_validated_row(conn, tenant_id=tenant_id, case_id=case_id)
        chain = [case_id]
        seen = {case_id}
        current = case_id
        while True:
            row = conn.execute(
                """
                SELECT parent_case_id FROM capacity_commitment_case_revisions
                WHERE tenant_id=? AND child_case_id=?
                """,
                (tenant_id, current),
            ).fetchone()
            if row is None:
                break
            parent_case_id = self._validate_case_id(row["parent_case_id"])
            if parent_case_id in seen:
                raise RuntimeError("capacity revision lineage cycle detected")
            self._load_validated_row(conn, tenant_id=tenant_id, case_id=parent_case_id)
            seen.add(parent_case_id)
            chain.append(parent_case_id)
            current = parent_case_id
        chain.reverse()
        return chain

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

    def create_revision(self, state: AssistedCaseState, *, parent_case_id: str) -> bool:
        """Atomically create a new immutable child revision linked to one parent.

        The child must use a new case_id. The parent must exist in the same
        tenant. Exact retries of the same child snapshot + parent are idempotent;
        any changed child source state or changed parent is a conflict.
        """

        parent_case_id = self._validate_case_id(parent_case_id)
        child_case_id = self._validate_case_id(state.recovery_case.case_id)
        if parent_case_id == child_case_id:
            raise ValueError("revision child case_id must differ from parent_case_id")
        evaluate_recoverability(state.recovery_case)
        snapshot = dump_state(state)
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._validated_lineage_chain(
                conn,
                tenant_id=state.tenant_id,
                case_id=parent_case_id,
            )
            existing = conn.execute(
                """
                SELECT snapshot, engine_version FROM capacity_commitment_cases
                WHERE tenant_id=? AND case_id=?
                """,
                (state.tenant_id, child_case_id),
            ).fetchone()
            if existing is not None:
                if existing["engine_version"] != ENGINE_VERSION:
                    raise RuntimeError("case requires explicit reassessment for engine version drift")
                link = conn.execute(
                    """
                    SELECT parent_case_id FROM capacity_commitment_case_revisions
                    WHERE tenant_id=? AND child_case_id=?
                    """,
                    (state.tenant_id, child_case_id),
                ).fetchone()
                if existing["snapshot"] == snapshot and link is not None and link["parent_case_id"] == parent_case_id:
                    return False
                raise FileExistsError("revision child already exists with different source state or parent")

            try:
                conn.execute(
                    """
                    INSERT INTO capacity_commitment_cases
                        (tenant_id, case_id, snapshot, engine_version, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (state.tenant_id, child_case_id, snapshot, ENGINE_VERSION, now),
                )
                conn.execute(
                    """
                    INSERT INTO capacity_commitment_case_revisions
                        (tenant_id, child_case_id, parent_case_id, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (state.tenant_id, child_case_id, parent_case_id, now),
                )
            except sqlite3.IntegrityError as exc:
                raise FileExistsError("revision child already exists") from exc
        return True

    def load(self, *, tenant_id: str, case_id: str) -> AssistedCaseState:
        if not tenant_id:
            raise ValueError("tenant_id and case_id are required")
        self._validate_case_id(case_id)
        with self._connect() as conn:
            return self._load_validated_row(conn, tenant_id=tenant_id, case_id=case_id)

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

    def revision_lineage(self, *, tenant_id: str, case_id: str) -> List[str]:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        case_id = self._validate_case_id(case_id)
        with self._connect() as conn:
            return self._validated_lineage_chain(conn, tenant_id=tenant_id, case_id=case_id)

    def list_revision_children(self, *, tenant_id: str, parent_case_id: str) -> List[str]:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        parent_case_id = self._validate_case_id(parent_case_id)
        with self._connect() as conn:
            self._load_validated_row(conn, tenant_id=tenant_id, case_id=parent_case_id)
            rows = conn.execute(
                """
                SELECT child_case_id FROM capacity_commitment_case_revisions
                WHERE tenant_id=? AND parent_case_id=? ORDER BY child_case_id
                """,
                (tenant_id, parent_case_id),
            ).fetchall()
            children = [row["child_case_id"] for row in rows]
            for child_case_id in children:
                self._validate_case_id(child_case_id)
                self._load_validated_row(conn, tenant_id=tenant_id, case_id=child_case_id)
            return children

    def backup_to(self, destination_path: str) -> None:
        if not destination_path:
            raise ValueError("destination_path is required")
        destination = str(Path(destination_path))
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        if _same_physical_file(destination, self.db_path):
            raise ValueError("backup destination must differ from source")
        with self._connect() as source, sqlite3.connect(destination) as dest:
            source.backup(dest)

    def restore_from(self, source_path: str) -> None:
        """Restore validated immutable cases and revision lineage.

        The source database schema is never copied over the live database. Older
        valid backups without the lineage table remain restorable as root-only
        histories. When lineage exists, every parent/child relation is validated
        before the live repository is mutated.
        """

        if not source_path or not Path(source_path).is_file():
            raise ValueError("restore source does not exist")
        if _same_physical_file(source_path, self.db_path):
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
            schema_error = self._schema_error(source)
            if schema_error:
                raise ValueError(f"restore source {schema_error}")

            rows = source.execute(
                """
                SELECT tenant_id, case_id, snapshot, engine_version, updated_at
                FROM capacity_commitment_cases
                ORDER BY tenant_id, case_id
                """
            ).fetchall()
            validated_rows = []
            case_keys = set()
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
                case_keys.add((row["tenant_id"], row["case_id"]))
                validated_rows.append(
                    (
                        row["tenant_id"],
                        row["case_id"],
                        row["snapshot"],
                        row["engine_version"],
                        row["updated_at"],
                    )
                )

            lineage_table = source.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='capacity_commitment_case_revisions'
                """
            ).fetchone()
            lineage_rows = []
            if lineage_table is not None:
                lineage_error = self._lineage_schema_error(source)
                if lineage_error:
                    raise ValueError(f"restore source {lineage_error}")
                raw_lineage = source.execute(
                    """
                    SELECT tenant_id, child_case_id, parent_case_id, created_at
                    FROM capacity_commitment_case_revisions
                    ORDER BY tenant_id, child_case_id
                    """
                ).fetchall()
                parent_by_child = {}
                for row in raw_lineage:
                    try:
                        child_case_id = self._validate_case_id(row["child_case_id"])
                        parent_case_id = self._validate_case_id(row["parent_case_id"])
                    except ValueError as exc:
                        raise ValueError("restore source has invalid revision lineage identity") from exc
                    tenant_id = row["tenant_id"]
                    if child_case_id == parent_case_id:
                        raise ValueError("restore source revision lineage self-cycle")
                    if (tenant_id, child_case_id) not in case_keys or (tenant_id, parent_case_id) not in case_keys:
                        raise ValueError("restore source revision lineage references missing or cross-tenant case")
                    parent_by_child[(tenant_id, child_case_id)] = parent_case_id
                    lineage_rows.append((tenant_id, child_case_id, parent_case_id, row["created_at"]))

                for tenant_id, child_case_id in parent_by_child:
                    seen = set()
                    current = child_case_id
                    while (tenant_id, current) in parent_by_child:
                        if current in seen:
                            raise ValueError("restore source revision lineage cycle")
                        seen.add(current)
                        current = parent_by_child[(tenant_id, current)]

            try:
                with self._connect() as destination:
                    schema_error = self._schema_error(destination)
                    if schema_error:
                        raise RuntimeError(f"{schema_error}; explicit migration required")
                    lineage_error = self._lineage_schema_error(destination)
                    if lineage_error:
                        raise RuntimeError(f"{lineage_error}; explicit migration required")
                    destination.execute("DELETE FROM capacity_commitment_case_revisions")
                    destination.execute("DELETE FROM capacity_commitment_cases")
                    destination.executemany(
                        """
                        INSERT INTO capacity_commitment_cases
                            (tenant_id, case_id, snapshot, engine_version, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        validated_rows,
                    )
                    destination.executemany(
                        """
                        INSERT INTO capacity_commitment_case_revisions
                            (tenant_id, child_case_id, parent_case_id, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        lineage_rows,
                    )
            except sqlite3.IntegrityError as exc:
                raise ValueError("restore source violates canonical capacity constraints") from exc
        finally:
            source.close()
