from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List

from .engine import ENGINE_VERSION, evaluate_recoverability
from .evidence import (
    EvidenceKind,
    EvidenceSource,
    ExtractedFact,
    FactType,
    ReviewState,
    validate_fact,
    validate_source,
)
from .identifiers import CASE_ID_ADDRESSABILITY_ERROR, is_addressable_case_id
from .service_ops import (
    MonitoringPlan,
    SupportCategory,
    SupportEvent,
    SupportEventType,
    SupportTicket,
    validate_monitor,
    validate_support_event,
    validate_ticket,
)
from .state import AssistedCaseState, dump_state, load_state
from .workflow import (
    Engagement,
    WorkflowEvent,
    WorkflowEventType,
    validate_engagement,
    validate_event,
)


_SCHEMA_COLUMNS = {"tenant_id", "case_id", "snapshot", "engine_version", "updated_at"}
_PRIMARY_KEY = ("tenant_id", "case_id")
_TABLE_NAME = "capacity_commitment_cases"
_LINEAGE_SCHEMA_COLUMNS = {"tenant_id", "child_case_id", "parent_case_id", "created_at"}
_LINEAGE_PRIMARY_KEY = ("tenant_id", "child_case_id")
_LINEAGE_TABLE_NAME = "capacity_commitment_case_revisions"

_EVIDENCE_SOURCE_COLUMNS = {
    "tenant_id",
    "evidence_id",
    "kind",
    "display_name",
    "external_ref",
    "sha256",
    "captured_at",
    "created_at",
}
_EVIDENCE_SOURCE_PK = ("tenant_id", "evidence_id")
_EVIDENCE_SOURCE_TABLE = "capacity_commitment_evidence_sources"
_EVIDENCE_FACT_COLUMNS = {
    "tenant_id",
    "fact_id",
    "evidence_id",
    "fact_type",
    "raw_value",
    "normalized_value",
    "scope_ref",
    "page_ref",
    "clause_ref",
    "review_state",
    "created_at",
    "reviewed_at",
}
_EVIDENCE_FACT_PK = ("tenant_id", "fact_id")
_EVIDENCE_FACT_TABLE = "capacity_commitment_evidence_facts"
_EVIDENCE_FACT_NULLABLE = {"scope_ref", "page_ref", "clause_ref", "reviewed_at"}

_ENGAGEMENT_TABLE = "capacity_commitment_engagements"
_ENGAGEMENT_COLUMNS = {
    "tenant_id",
    "engagement_id",
    "company_id",
    "customer_id",
    "program_id",
    "currency",
    "created_at",
}
_ENGAGEMENT_PK = ("tenant_id", "engagement_id")
_WORKFLOW_EVENT_TABLE = "capacity_commitment_workflow_events"
_WORKFLOW_EVENT_COLUMNS = {
    "tenant_id",
    "event_id",
    "engagement_id",
    "event_type",
    "occurred_at",
    "case_id",
    "amount",
    "currency",
    "external_ref",
    "note",
    "created_at",
}
_WORKFLOW_EVENT_PK = ("tenant_id", "event_id")
_WORKFLOW_EVENT_NULLABLE = {"case_id", "amount", "currency", "external_ref", "note"}

_MONITOR_TABLE = "capacity_commitment_monitoring_plans"
_MONITOR_COLUMNS = {
    "tenant_id",
    "monitor_id",
    "engagement_id",
    "case_id",
    "cadence_days",
    "next_check_on",
    "supersedes_monitor_id",
    "created_at",
}
_MONITOR_PK = ("tenant_id", "monitor_id")
_MONITOR_NULLABLE = {"supersedes_monitor_id"}
_SUPPORT_TICKET_TABLE = "capacity_commitment_support_tickets"
_SUPPORT_TICKET_COLUMNS = {
    "tenant_id",
    "ticket_id",
    "engagement_id",
    "category",
    "summary",
    "opened_at",
    "case_id",
    "created_at",
}
_SUPPORT_TICKET_PK = ("tenant_id", "ticket_id")
_SUPPORT_TICKET_NULLABLE = {"case_id"}
_SUPPORT_EVENT_TABLE = "capacity_commitment_support_events"
_SUPPORT_EVENT_COLUMNS = {
    "tenant_id",
    "support_event_id",
    "ticket_id",
    "event_type",
    "occurred_at",
    "note",
    "created_at",
}
_SUPPORT_EVENT_PK = ("tenant_id", "support_event_id")
_SUPPORT_EVENT_NULLABLE = {"note"}


def _same_physical_file(first: str, second: str) -> bool:
    if os.path.abspath(first) == os.path.abspath(second):
        return True
    try:
        return os.path.samefile(first, second)
    except (FileNotFoundError, OSError):
        return False


class CapacityRepository:
    """Tenant-scoped durable repository for the Capacity Commitment case system.

    Case snapshots, revisions, evidence provenance and the customer-operation
    ledgers share one SQLite durability boundary. Case source state is immutable;
    changed evidence/economics are represented by new linked revisions. Backup
    and restore operate on the complete known operational state, never just the
    headline case rows.
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
    def _strict_table_schema_error(
        conn: sqlite3.Connection,
        *,
        table: str,
        expected_columns: set[str],
        expected_pk: tuple[str, ...],
        nullable: set[str] | None = None,
        label: str | None = None,
    ) -> str | None:
        label = label or table
        nullable = nullable or set()
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        if not rows:
            return f"{label} schema is missing"
        names = {row["name"] for row in rows}
        missing = expected_columns - names
        if missing:
            return f"{label} schema lacks required columns"
        extra = names - expected_columns
        if extra:
            return f"{label} schema has unknown columns and requires explicit migration"
        primary_key = tuple(
            row["name"]
            for row in sorted(
                (row for row in rows if row["pk"]), key=lambda row: row["pk"]
            )
        )
        if primary_key != expected_pk:
            return f"{label} primary key mismatch"
        for row in rows:
            if str(row["type"] or "").upper() != "TEXT":
                return f"{label} columns must use TEXT storage"
            should_be_nullable = row["name"] in nullable
            if should_be_nullable:
                if row["notnull"] != 0:
                    return f"{label} nullable column constraint mismatch"
            elif row["notnull"] != 1:
                return f"{label} required columns must be NOT NULL"
        if conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=?",
            (table,),
        ).fetchall():
            return f"{label} contains unexpected trigger"
        if conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
            (table,),
        ).fetchall():
            return f"{label} contains unexpected index"
        if conn.execute(f"PRAGMA foreign_key_list({table})").fetchall():
            return f"{label} contains unexpected foreign key"
        return None

    @classmethod
    def _schema_error(cls, conn: sqlite3.Connection) -> str | None:
        error = cls._strict_table_schema_error(
            conn,
            table=_TABLE_NAME,
            expected_columns=_SCHEMA_COLUMNS,
            expected_pk=_PRIMARY_KEY,
            label="capacity schema",
        )
        if error == "capacity schema primary key mismatch":
            return "capacity schema primary key must be (tenant_id, case_id)"
        return error

    @classmethod
    def _lineage_schema_error(cls, conn: sqlite3.Connection) -> str | None:
        error = cls._strict_table_schema_error(
            conn,
            table=_LINEAGE_TABLE_NAME,
            expected_columns=_LINEAGE_SCHEMA_COLUMNS,
            expected_pk=_LINEAGE_PRIMARY_KEY,
            label="revision lineage schema",
        )
        if error == "revision lineage schema primary key mismatch":
            return "revision lineage primary key must be (tenant_id, child_case_id)"
        return error

    @classmethod
    def _evidence_schema_error(
        cls,
        conn: sqlite3.Connection,
        *,
        table: str,
        expected_columns: set[str],
        expected_pk: tuple[str, ...],
        nullable: set[str] | None = None,
    ) -> str | None:
        return cls._strict_table_schema_error(
            conn,
            table=table,
            expected_columns=expected_columns,
            expected_pk=expected_pk,
            nullable=nullable,
            label=table,
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _create_evidence_schema(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS capacity_commitment_evidence_sources (
                tenant_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                display_name TEXT NOT NULL,
                external_ref TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, evidence_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS capacity_commitment_evidence_facts (
                tenant_id TEXT NOT NULL,
                fact_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                fact_type TEXT NOT NULL,
                raw_value TEXT NOT NULL,
                normalized_value TEXT NOT NULL,
                scope_ref TEXT,
                page_ref TEXT,
                clause_ref TEXT,
                review_state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                PRIMARY KEY (tenant_id, fact_id)
            )
            """
        )

    @staticmethod
    def _create_operational_schema(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS capacity_commitment_engagements (
                tenant_id TEXT NOT NULL,
                engagement_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                program_id TEXT NOT NULL,
                currency TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, engagement_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS capacity_commitment_workflow_events (
                tenant_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                engagement_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                case_id TEXT,
                amount TEXT,
                currency TEXT,
                external_ref TEXT,
                note TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, event_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS capacity_commitment_monitoring_plans (
                tenant_id TEXT NOT NULL,
                monitor_id TEXT NOT NULL,
                engagement_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                cadence_days TEXT NOT NULL,
                next_check_on TEXT NOT NULL,
                supersedes_monitor_id TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, monitor_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS capacity_commitment_support_tickets (
                tenant_id TEXT NOT NULL,
                ticket_id TEXT NOT NULL,
                engagement_id TEXT NOT NULL,
                category TEXT NOT NULL,
                summary TEXT NOT NULL,
                opened_at TEXT NOT NULL,
                case_id TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, ticket_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS capacity_commitment_support_events (
                tenant_id TEXT NOT NULL,
                support_event_id TEXT NOT NULL,
                ticket_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, support_event_id)
            )
            """
        )

    @classmethod
    def _known_schema_errors(cls, conn: sqlite3.Connection) -> list[str]:
        checks = [
            cls._schema_error(conn),
            cls._lineage_schema_error(conn),
            cls._evidence_schema_error(
                conn,
                table=_EVIDENCE_SOURCE_TABLE,
                expected_columns=_EVIDENCE_SOURCE_COLUMNS,
                expected_pk=_EVIDENCE_SOURCE_PK,
            ),
            cls._evidence_schema_error(
                conn,
                table=_EVIDENCE_FACT_TABLE,
                expected_columns=_EVIDENCE_FACT_COLUMNS,
                expected_pk=_EVIDENCE_FACT_PK,
                nullable=_EVIDENCE_FACT_NULLABLE,
            ),
            cls._strict_table_schema_error(
                conn,
                table=_ENGAGEMENT_TABLE,
                expected_columns=_ENGAGEMENT_COLUMNS,
                expected_pk=_ENGAGEMENT_PK,
            ),
            cls._strict_table_schema_error(
                conn,
                table=_WORKFLOW_EVENT_TABLE,
                expected_columns=_WORKFLOW_EVENT_COLUMNS,
                expected_pk=_WORKFLOW_EVENT_PK,
                nullable=_WORKFLOW_EVENT_NULLABLE,
            ),
            cls._strict_table_schema_error(
                conn,
                table=_MONITOR_TABLE,
                expected_columns=_MONITOR_COLUMNS,
                expected_pk=_MONITOR_PK,
                nullable=_MONITOR_NULLABLE,
            ),
            cls._strict_table_schema_error(
                conn,
                table=_SUPPORT_TICKET_TABLE,
                expected_columns=_SUPPORT_TICKET_COLUMNS,
                expected_pk=_SUPPORT_TICKET_PK,
                nullable=_SUPPORT_TICKET_NULLABLE,
            ),
            cls._strict_table_schema_error(
                conn,
                table=_SUPPORT_EVENT_TABLE,
                expected_columns=_SUPPORT_EVENT_COLUMNS,
                expected_pk=_SUPPORT_EVENT_PK,
                nullable=_SUPPORT_EVENT_NULLABLE,
            ),
        ]
        return [error for error in checks if error]

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
            self._create_evidence_schema(conn)
            self._create_operational_schema(conn)
            errors = self._known_schema_errors(conn)
            if errors:
                raise RuntimeError(f"{errors[0]}; explicit migration required")

    @staticmethod
    def _assert_revision_identity(parent: AssistedCaseState, child: AssistedCaseState) -> None:
        identity = {
            "company_id": (parent.company_id, child.company_id),
            "customer_id": (parent.customer_id, child.customer_id),
            "program_id": (parent.program_id, child.program_id),
            "currency": (parent.recovery_case.currency, child.recovery_case.currency),
        }
        mismatches = [name for name, values in identity.items() if values[0] != values[1]]
        if mismatches:
            raise ValueError("revision identity mismatch: " + ", ".join(sorted(mismatches)))

    @staticmethod
    def _assert_case_engagement_identity(state: AssistedCaseState, engagement: Engagement) -> None:
        mismatches = []
        if state.company_id != engagement.company_id:
            mismatches.append("company_id")
        if state.customer_id != engagement.customer_id:
            mismatches.append("customer_id")
        if state.program_id != engagement.program_id:
            mismatches.append("program_id")
        if state.recovery_case.currency.upper() != engagement.currency:
            mismatches.append("currency")
        if mismatches:
            raise ValueError("case does not match engagement: " + ", ".join(mismatches))

    def _load_validated_row(
        self,
        conn: sqlite3.Connection,
        *,
        tenant_id: str,
        case_id: str,
    ) -> AssistedCaseState:
        row = conn.execute(
            "SELECT snapshot, engine_version FROM capacity_commitment_cases "
            "WHERE tenant_id=? AND case_id=?",
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
        child_state = self._load_validated_row(conn, tenant_id=tenant_id, case_id=case_id)
        chain = [case_id]
        seen = {case_id}
        current = case_id
        while True:
            row = conn.execute(
                "SELECT parent_case_id FROM capacity_commitment_case_revisions "
                "WHERE tenant_id=? AND child_case_id=?",
                (tenant_id, current),
            ).fetchone()
            if row is None:
                break
            parent_case_id = self._validate_case_id(row["parent_case_id"])
            if parent_case_id in seen:
                raise RuntimeError("capacity revision lineage cycle detected")
            parent_state = self._load_validated_row(
                conn, tenant_id=tenant_id, case_id=parent_case_id
            )
            try:
                self._assert_revision_identity(parent_state, child_state)
            except ValueError as exc:
                raise RuntimeError("capacity revision lineage identity mismatch") from exc
            seen.add(parent_case_id)
            chain.append(parent_case_id)
            current = parent_case_id
            child_state = parent_state
        chain.reverse()
        return chain

    def save(self, state: AssistedCaseState) -> bool:
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
                    "SELECT snapshot, engine_version FROM capacity_commitment_cases "
                    "WHERE tenant_id=? AND case_id=?",
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
                conn, tenant_id=state.tenant_id, case_id=parent_case_id
            )
            parent_state = self._load_validated_row(
                conn, tenant_id=state.tenant_id, case_id=parent_case_id
            )
            self._assert_revision_identity(parent_state, state)
            existing = conn.execute(
                "SELECT snapshot, engine_version FROM capacity_commitment_cases "
                "WHERE tenant_id=? AND case_id=?",
                (state.tenant_id, child_case_id),
            ).fetchone()
            if existing is not None:
                if existing["engine_version"] != ENGINE_VERSION:
                    raise RuntimeError("case requires explicit reassessment for engine version drift")
                link = conn.execute(
                    "SELECT parent_case_id FROM capacity_commitment_case_revisions "
                    "WHERE tenant_id=? AND child_case_id=?",
                    (state.tenant_id, child_case_id),
                ).fetchone()
                if (
                    existing["snapshot"] == snapshot
                    and link is not None
                    and link["parent_case_id"] == parent_case_id
                ):
                    return False
                raise FileExistsError(
                    "revision child already exists with different source state or parent"
                )
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
                "SELECT case_id FROM capacity_commitment_cases WHERE tenant_id=? ORDER BY case_id",
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
            parent_state = self._load_validated_row(
                conn, tenant_id=tenant_id, case_id=parent_case_id
            )
            rows = conn.execute(
                "SELECT child_case_id FROM capacity_commitment_case_revisions "
                "WHERE tenant_id=? AND parent_case_id=? ORDER BY child_case_id",
                (tenant_id, parent_case_id),
            ).fetchall()
            children = [row["child_case_id"] for row in rows]
            for child_case_id in children:
                self._validate_case_id(child_case_id)
                child_state = self._load_validated_row(
                    conn, tenant_id=tenant_id, case_id=child_case_id
                )
                try:
                    self._assert_revision_identity(parent_state, child_state)
                except ValueError as exc:
                    raise RuntimeError("capacity revision lineage identity mismatch") from exc
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

    @staticmethod
    def _table_present(conn: sqlite3.Connection, table: str) -> bool:
        return (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            is not None
        )

    @classmethod
    def _require_complete_group(
        cls, conn: sqlite3.Connection, tables: tuple[str, ...], label: str
    ) -> bool:
        present = [cls._table_present(conn, table) for table in tables]
        if any(present) and not all(present):
            raise ValueError(f"restore source has incomplete {label} schema")
        return all(present)

    def restore_from(self, source_path: str) -> None:
        """Restore the complete known Capacity operational snapshot atomically.

        Every source row and cross-table relation is validated before destination
        mutation. Historical backups that legitimately predate a newer table group
        are accepted as empty for that group, which also clears newer live rows.
        """

        if not source_path or not Path(source_path).is_file():
            raise ValueError("restore source does not exist")
        if _same_physical_file(source_path, self.db_path):
            raise ValueError("restore source must differ from destination")

        source = sqlite3.connect(source_path)
        source.row_factory = sqlite3.Row
        try:
            if not self._table_present(source, _TABLE_NAME):
                raise ValueError("restore source lacks capacity schema")
            schema_error = self._schema_error(source)
            if schema_error:
                raise ValueError(f"restore source {schema_error}")

            case_rows = source.execute(
                """
                SELECT tenant_id, case_id, snapshot, engine_version, updated_at
                FROM capacity_commitment_cases ORDER BY tenant_id, case_id
                """
            ).fetchall()
            validated_cases = []
            case_states: dict[tuple[str, str], AssistedCaseState] = {}
            for row in case_rows:
                try:
                    case_id = self._validate_case_id(row["case_id"])
                    if row["engine_version"] != ENGINE_VERSION:
                        raise ValueError("restore source requires explicit engine reassessment")
                    state = load_state(row["snapshot"], expected_tenant_id=row["tenant_id"])
                    if state.recovery_case.case_id != case_id:
                        raise ValueError("restore source case identity mismatch")
                    evaluate_recoverability(state.recovery_case)
                except ValueError:
                    raise
                except Exception as exc:
                    raise ValueError("restore source has invalid capacity case") from exc
                key = (row["tenant_id"], case_id)
                case_states[key] = state
                validated_cases.append(
                    (
                        row["tenant_id"],
                        case_id,
                        row["snapshot"],
                        row["engine_version"],
                        row["updated_at"],
                    )
                )

            validated_lineage = []
            parent_by_child: dict[tuple[str, str], str] = {}
            if self._table_present(source, _LINEAGE_TABLE_NAME):
                error = self._lineage_schema_error(source)
                if error:
                    raise ValueError(f"restore source {error}")
                for row in source.execute(
                    """
                    SELECT tenant_id, child_case_id, parent_case_id, created_at
                    FROM capacity_commitment_case_revisions
                    ORDER BY tenant_id, child_case_id
                    """
                ).fetchall():
                    tenant_id = row["tenant_id"]
                    try:
                        child = self._validate_case_id(row["child_case_id"])
                        parent = self._validate_case_id(row["parent_case_id"])
                    except ValueError as exc:
                        raise ValueError(
                            "restore source has invalid revision lineage identity"
                        ) from exc
                    if child == parent:
                        raise ValueError("restore source revision lineage self-cycle")
                    child_state = case_states.get((tenant_id, child))
                    parent_state = case_states.get((tenant_id, parent))
                    if child_state is None or parent_state is None:
                        raise ValueError(
                            "restore source revision lineage references missing or cross-tenant case"
                        )
                    try:
                        self._assert_revision_identity(parent_state, child_state)
                    except ValueError as exc:
                        raise ValueError(
                            "restore source revision lineage identity mismatch"
                        ) from exc
                    parent_by_child[(tenant_id, child)] = parent
                    validated_lineage.append(
                        (tenant_id, child, parent, row["created_at"])
                    )
                for tenant_id, child in parent_by_child:
                    seen = set()
                    current = child
                    while (tenant_id, current) in parent_by_child:
                        if current in seen:
                            raise ValueError("restore source revision lineage cycle")
                        seen.add(current)
                        current = parent_by_child[(tenant_id, current)]

            evidence_group = self._require_complete_group(
                source,
                (_EVIDENCE_SOURCE_TABLE, _EVIDENCE_FACT_TABLE),
                "evidence",
            )
            validated_sources = []
            validated_facts = []
            evidence_keys: set[tuple[str, str]] = set()
            if evidence_group:
                source_error = self._evidence_schema_error(
                    source,
                    table=_EVIDENCE_SOURCE_TABLE,
                    expected_columns=_EVIDENCE_SOURCE_COLUMNS,
                    expected_pk=_EVIDENCE_SOURCE_PK,
                )
                fact_error = self._evidence_schema_error(
                    source,
                    table=_EVIDENCE_FACT_TABLE,
                    expected_columns=_EVIDENCE_FACT_COLUMNS,
                    expected_pk=_EVIDENCE_FACT_PK,
                    nullable=_EVIDENCE_FACT_NULLABLE,
                )
                if source_error:
                    raise ValueError(f"restore source {source_error}")
                if fact_error:
                    raise ValueError(f"restore source {fact_error}")
                for row in source.execute(
                    """
                    SELECT tenant_id, evidence_id, kind, display_name, external_ref,
                           sha256, captured_at, created_at
                    FROM capacity_commitment_evidence_sources
                    ORDER BY tenant_id, evidence_id
                    """
                ).fetchall():
                    try:
                        item = validate_source(
                            EvidenceSource(
                                tenant_id=row["tenant_id"],
                                evidence_id=row["evidence_id"],
                                kind=EvidenceKind(row["kind"]),
                                display_name=row["display_name"],
                                external_ref=row["external_ref"],
                                sha256=row["sha256"],
                                captured_at=row["captured_at"],
                            )
                        )
                    except (ValueError, TypeError) as exc:
                        raise ValueError(
                            "restore source has invalid evidence provenance"
                        ) from exc
                    evidence_keys.add((item.tenant_id, item.evidence_id))
                    validated_sources.append(
                        (
                            item.tenant_id,
                            item.evidence_id,
                            item.kind.value,
                            item.display_name,
                            item.external_ref,
                            item.sha256,
                            item.captured_at,
                            row["created_at"],
                        )
                    )
                for row in source.execute(
                    """
                    SELECT tenant_id, fact_id, evidence_id, fact_type, raw_value,
                           normalized_value, scope_ref, page_ref, clause_ref,
                           review_state, created_at, reviewed_at
                    FROM capacity_commitment_evidence_facts
                    ORDER BY tenant_id, fact_id
                    """
                ).fetchall():
                    try:
                        item = validate_fact(
                            ExtractedFact(
                                tenant_id=row["tenant_id"],
                                fact_id=row["fact_id"],
                                evidence_id=row["evidence_id"],
                                fact_type=FactType(row["fact_type"]),
                                raw_value=row["raw_value"],
                                normalized_value=row["normalized_value"],
                                scope_ref=row["scope_ref"],
                                page_ref=row["page_ref"],
                                clause_ref=row["clause_ref"],
                                review_state=ReviewState(row["review_state"]),
                            )
                        )
                    except (ValueError, TypeError) as exc:
                        raise ValueError("restore source has invalid evidence fact") from exc
                    if (item.tenant_id, item.evidence_id) not in evidence_keys:
                        raise ValueError(
                            "restore source evidence fact references missing or cross-tenant source"
                        )
                    if item.normalized_value != row["normalized_value"]:
                        raise ValueError(
                            "restore source evidence fact is not canonically normalized"
                        )
                    validated_facts.append(
                        (
                            item.tenant_id,
                            item.fact_id,
                            item.evidence_id,
                            item.fact_type.value,
                            item.raw_value,
                            item.normalized_value,
                            item.scope_ref,
                            item.page_ref,
                            item.clause_ref,
                            item.review_state.value,
                            row["created_at"],
                            row["reviewed_at"],
                        )
                    )

            workflow_group = self._require_complete_group(
                source, (_ENGAGEMENT_TABLE, _WORKFLOW_EVENT_TABLE), "workflow"
            )
            validated_engagements = []
            validated_events = []
            engagement_by_key: dict[tuple[str, str], Engagement] = {}
            if workflow_group:
                for table, columns, pk, nullable in (
                    (_ENGAGEMENT_TABLE, _ENGAGEMENT_COLUMNS, _ENGAGEMENT_PK, set()),
                    (
                        _WORKFLOW_EVENT_TABLE,
                        _WORKFLOW_EVENT_COLUMNS,
                        _WORKFLOW_EVENT_PK,
                        _WORKFLOW_EVENT_NULLABLE,
                    ),
                ):
                    error = self._strict_table_schema_error(
                        source,
                        table=table,
                        expected_columns=columns,
                        expected_pk=pk,
                        nullable=nullable,
                    )
                    if error:
                        raise ValueError(f"restore source {error}")
                for row in source.execute(
                    """
                    SELECT tenant_id, engagement_id, company_id, customer_id,
                           program_id, currency, created_at
                    FROM capacity_commitment_engagements
                    ORDER BY tenant_id, engagement_id
                    """
                ).fetchall():
                    try:
                        item = validate_engagement(
                            Engagement(
                                tenant_id=row["tenant_id"],
                                engagement_id=row["engagement_id"],
                                company_id=row["company_id"],
                                customer_id=row["customer_id"],
                                program_id=row["program_id"],
                                currency=row["currency"],
                            )
                        )
                    except ValueError as exc:
                        raise ValueError("restore source has invalid engagement") from exc
                    engagement_by_key[(item.tenant_id, item.engagement_id)] = item
                    validated_engagements.append(
                        (
                            item.tenant_id,
                            item.engagement_id,
                            item.company_id,
                            item.customer_id,
                            item.program_id,
                            item.currency,
                            row["created_at"],
                        )
                    )
                for row in source.execute(
                    """
                    SELECT tenant_id, event_id, engagement_id, event_type,
                           occurred_at, case_id, amount, currency, external_ref,
                           note, created_at
                    FROM capacity_commitment_workflow_events
                    ORDER BY tenant_id, event_id
                    """
                ).fetchall():
                    amount = None
                    if row["amount"] is not None:
                        try:
                            amount = Decimal(row["amount"])
                        except InvalidOperation as exc:
                            raise ValueError(
                                "restore source has invalid workflow amount"
                            ) from exc
                    try:
                        item = validate_event(
                            WorkflowEvent(
                                tenant_id=row["tenant_id"],
                                event_id=row["event_id"],
                                engagement_id=row["engagement_id"],
                                event_type=WorkflowEventType(row["event_type"]),
                                occurred_at=row["occurred_at"],
                                case_id=row["case_id"],
                                amount=amount,
                                currency=row["currency"],
                                external_ref=row["external_ref"],
                                note=row["note"],
                            )
                        )
                    except (ValueError, TypeError) as exc:
                        raise ValueError("restore source has invalid workflow event") from exc
                    engagement = engagement_by_key.get(
                        (item.tenant_id, item.engagement_id)
                    )
                    if engagement is None:
                        raise ValueError(
                            "restore source workflow event references missing or cross-tenant engagement"
                        )
                    if item.currency is not None and item.currency != engagement.currency:
                        raise ValueError(
                            "restore source workflow event currency does not match engagement"
                        )
                    if item.amount is not None and format(item.amount, "f") != row["amount"]:
                        raise ValueError(
                            "restore source workflow amount is not canonically normalized"
                        )
                    if item.case_id is not None:
                        state = case_states.get((item.tenant_id, item.case_id))
                        if state is None:
                            raise ValueError(
                                "restore source workflow event references missing or cross-tenant case"
                            )
                        try:
                            self._assert_case_engagement_identity(state, engagement)
                        except ValueError as exc:
                            raise ValueError(
                                "restore source workflow case/engagement identity mismatch"
                            ) from exc
                    validated_events.append(
                        (
                            item.tenant_id,
                            item.event_id,
                            item.engagement_id,
                            item.event_type.value,
                            item.occurred_at,
                            item.case_id,
                            None if item.amount is None else format(item.amount, "f"),
                            item.currency,
                            item.external_ref,
                            item.note,
                            row["created_at"],
                        )
                    )

            service_group = self._require_complete_group(
                source,
                (_MONITOR_TABLE, _SUPPORT_TICKET_TABLE, _SUPPORT_EVENT_TABLE),
                "service operations",
            )
            validated_monitors = []
            validated_tickets = []
            validated_support_events = []
            if service_group:
                for table, columns, pk, nullable in (
                    (_MONITOR_TABLE, _MONITOR_COLUMNS, _MONITOR_PK, _MONITOR_NULLABLE),
                    (
                        _SUPPORT_TICKET_TABLE,
                        _SUPPORT_TICKET_COLUMNS,
                        _SUPPORT_TICKET_PK,
                        _SUPPORT_TICKET_NULLABLE,
                    ),
                    (
                        _SUPPORT_EVENT_TABLE,
                        _SUPPORT_EVENT_COLUMNS,
                        _SUPPORT_EVENT_PK,
                        _SUPPORT_EVENT_NULLABLE,
                    ),
                ):
                    error = self._strict_table_schema_error(
                        source,
                        table=table,
                        expected_columns=columns,
                        expected_pk=pk,
                        nullable=nullable,
                    )
                    if error:
                        raise ValueError(f"restore source {error}")

                monitor_by_key: dict[tuple[str, str], MonitoringPlan] = {}
                for row in source.execute(
                    """
                    SELECT tenant_id, monitor_id, engagement_id, case_id,
                           cadence_days, next_check_on, supersedes_monitor_id,
                           created_at
                    FROM capacity_commitment_monitoring_plans
                    ORDER BY tenant_id, monitor_id
                    """
                ).fetchall():
                    try:
                        cadence_days = int(row["cadence_days"])
                        item = validate_monitor(
                            MonitoringPlan(
                                tenant_id=row["tenant_id"],
                                monitor_id=row["monitor_id"],
                                engagement_id=row["engagement_id"],
                                case_id=row["case_id"],
                                cadence_days=cadence_days,
                                next_check_on=row["next_check_on"],
                                supersedes_monitor_id=row["supersedes_monitor_id"],
                            )
                        )
                    except (ValueError, TypeError) as exc:
                        raise ValueError(
                            "restore source has invalid monitoring plan"
                        ) from exc
                    if str(item.cadence_days) != row["cadence_days"]:
                        raise ValueError(
                            "restore source monitoring cadence is not canonical"
                        )
                    engagement = engagement_by_key.get(
                        (item.tenant_id, item.engagement_id)
                    )
                    state = case_states.get((item.tenant_id, item.case_id))
                    if engagement is None or state is None:
                        raise ValueError(
                            "restore source monitoring plan references missing or cross-tenant scope"
                        )
                    try:
                        self._assert_case_engagement_identity(state, engagement)
                    except ValueError as exc:
                        raise ValueError(
                            "restore source monitoring case/engagement identity mismatch"
                        ) from exc
                    monitor_by_key[(item.tenant_id, item.monitor_id)] = item
                    validated_monitors.append(
                        (
                            item.tenant_id,
                            item.monitor_id,
                            item.engagement_id,
                            item.case_id,
                            str(item.cadence_days),
                            item.next_check_on,
                            item.supersedes_monitor_id,
                            row["created_at"],
                        )
                    )
                for item in monitor_by_key.values():
                    if item.supersedes_monitor_id is None:
                        continue
                    previous = monitor_by_key.get(
                        (item.tenant_id, item.supersedes_monitor_id)
                    )
                    if previous is None:
                        raise ValueError(
                            "restore source monitoring supersession references missing or cross-tenant plan"
                        )
                    if (
                        previous.engagement_id != item.engagement_id
                        or previous.case_id != item.case_id
                    ):
                        raise ValueError(
                            "restore source monitoring supersession changes scope"
                        )
                for key, item in monitor_by_key.items():
                    seen = set()
                    current = item
                    while current.supersedes_monitor_id is not None:
                        if current.monitor_id in seen:
                            raise ValueError(
                                "restore source monitoring supersession cycle"
                            )
                        seen.add(current.monitor_id)
                        current = monitor_by_key[
                            (current.tenant_id, current.supersedes_monitor_id)
                        ]

                ticket_keys: set[tuple[str, str]] = set()
                for row in source.execute(
                    """
                    SELECT tenant_id, ticket_id, engagement_id, category, summary,
                           opened_at, case_id, created_at
                    FROM capacity_commitment_support_tickets
                    ORDER BY tenant_id, ticket_id
                    """
                ).fetchall():
                    try:
                        item = validate_ticket(
                            SupportTicket(
                                tenant_id=row["tenant_id"],
                                ticket_id=row["ticket_id"],
                                engagement_id=row["engagement_id"],
                                category=SupportCategory(row["category"]),
                                summary=row["summary"],
                                opened_at=row["opened_at"],
                                case_id=row["case_id"],
                            )
                        )
                    except (ValueError, TypeError) as exc:
                        raise ValueError(
                            "restore source has invalid support ticket"
                        ) from exc
                    engagement = engagement_by_key.get(
                        (item.tenant_id, item.engagement_id)
                    )
                    if engagement is None:
                        raise ValueError(
                            "restore source support ticket references missing or cross-tenant engagement"
                        )
                    if item.case_id is not None:
                        state = case_states.get((item.tenant_id, item.case_id))
                        if state is None:
                            raise ValueError(
                                "restore source support ticket references missing or cross-tenant case"
                            )
                        try:
                            self._assert_case_engagement_identity(state, engagement)
                        except ValueError as exc:
                            raise ValueError(
                                "restore source support case/engagement identity mismatch"
                            ) from exc
                    ticket_keys.add((item.tenant_id, item.ticket_id))
                    validated_tickets.append(
                        (
                            item.tenant_id,
                            item.ticket_id,
                            item.engagement_id,
                            item.category.value,
                            item.summary,
                            item.opened_at,
                            item.case_id,
                            row["created_at"],
                        )
                    )

                for row in source.execute(
                    """
                    SELECT tenant_id, support_event_id, ticket_id, event_type,
                           occurred_at, note, created_at
                    FROM capacity_commitment_support_events
                    ORDER BY tenant_id, support_event_id
                    """
                ).fetchall():
                    try:
                        item = validate_support_event(
                            SupportEvent(
                                tenant_id=row["tenant_id"],
                                support_event_id=row["support_event_id"],
                                ticket_id=row["ticket_id"],
                                event_type=SupportEventType(row["event_type"]),
                                occurred_at=row["occurred_at"],
                                note=row["note"],
                            )
                        )
                    except (ValueError, TypeError) as exc:
                        raise ValueError(
                            "restore source has invalid support event"
                        ) from exc
                    if (item.tenant_id, item.ticket_id) not in ticket_keys:
                        raise ValueError(
                            "restore source support event references missing or cross-tenant ticket"
                        )
                    validated_support_events.append(
                        (
                            item.tenant_id,
                            item.support_event_id,
                            item.ticket_id,
                            item.event_type.value,
                            item.occurred_at,
                            item.note,
                            row["created_at"],
                        )
                    )

            try:
                with self._connect() as destination:
                    errors = self._known_schema_errors(destination)
                    if errors:
                        raise RuntimeError(f"{errors[0]}; explicit migration required")
                    for table in (
                        _SUPPORT_EVENT_TABLE,
                        _SUPPORT_TICKET_TABLE,
                        _MONITOR_TABLE,
                        _WORKFLOW_EVENT_TABLE,
                        _ENGAGEMENT_TABLE,
                        _EVIDENCE_FACT_TABLE,
                        _EVIDENCE_SOURCE_TABLE,
                        _LINEAGE_TABLE_NAME,
                        _TABLE_NAME,
                    ):
                        destination.execute(f"DELETE FROM {table}")

                    destination.executemany(
                        """
                        INSERT INTO capacity_commitment_cases
                        (tenant_id, case_id, snapshot, engine_version, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        validated_cases,
                    )
                    destination.executemany(
                        """
                        INSERT INTO capacity_commitment_case_revisions
                        (tenant_id, child_case_id, parent_case_id, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        validated_lineage,
                    )
                    destination.executemany(
                        """
                        INSERT INTO capacity_commitment_evidence_sources
                        (tenant_id, evidence_id, kind, display_name, external_ref,
                         sha256, captured_at, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        validated_sources,
                    )
                    destination.executemany(
                        """
                        INSERT INTO capacity_commitment_evidence_facts
                        (tenant_id, fact_id, evidence_id, fact_type, raw_value,
                         normalized_value, scope_ref, page_ref, clause_ref,
                         review_state, created_at, reviewed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        validated_facts,
                    )
                    destination.executemany(
                        """
                        INSERT INTO capacity_commitment_engagements
                        (tenant_id, engagement_id, company_id, customer_id,
                         program_id, currency, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        validated_engagements,
                    )
                    destination.executemany(
                        """
                        INSERT INTO capacity_commitment_workflow_events
                        (tenant_id, event_id, engagement_id, event_type, occurred_at,
                         case_id, amount, currency, external_ref, note, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        validated_events,
                    )
                    destination.executemany(
                        """
                        INSERT INTO capacity_commitment_monitoring_plans
                        (tenant_id, monitor_id, engagement_id, case_id, cadence_days,
                         next_check_on, supersedes_monitor_id, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        validated_monitors,
                    )
                    destination.executemany(
                        """
                        INSERT INTO capacity_commitment_support_tickets
                        (tenant_id, ticket_id, engagement_id, category, summary,
                         opened_at, case_id, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        validated_tickets,
                    )
                    destination.executemany(
                        """
                        INSERT INTO capacity_commitment_support_events
                        (tenant_id, support_event_id, ticket_id, event_type,
                         occurred_at, note, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        validated_support_events,
                    )
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    "restore source violates canonical capacity constraints"
                ) from exc
        finally:
            source.close()
