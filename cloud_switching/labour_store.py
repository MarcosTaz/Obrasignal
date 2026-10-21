from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import sqlite3
from pathlib import Path

from .labour import ActivityCode, LabourEntry, LabourSummary, summarize_labour


@dataclass(frozen=True)
class StoredLabourEntry:
    entry_id: int
    tenant_id: str
    case_id: str
    activity: ActivityCode
    hours: Decimal
    note: str
    recorded_at: datetime


class SQLiteLabourStore:
    BUSY_TIMEOUT_SECONDS = 15

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=self.BUSY_TIMEOUT_SECONDS)
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout={self.BUSY_TIMEOUT_SECONDS * 1000}")
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cloud_switching_labour_entries (
                    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    activity TEXT NOT NULL,
                    hours TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    recorded_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_cloud_switching_labour_case "
                "ON cloud_switching_labour_entries(tenant_id, case_id, entry_id)"
            )

    def add(self, *, tenant_id: str, entry: LabourEntry, recorded_at: datetime | None = None) -> StoredLabourEntry:
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        entry.validate()
        timestamp = recorded_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO cloud_switching_labour_entries
                    (tenant_id, case_id, activity, hours, note, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    entry.case_id,
                    entry.activity.value,
                    str(entry.hours),
                    entry.note,
                    timestamp.isoformat(),
                ),
            )
            entry_id = int(cursor.lastrowid)
        return StoredLabourEntry(
            entry_id=entry_id,
            tenant_id=tenant_id,
            case_id=entry.case_id,
            activity=entry.activity,
            hours=entry.hours,
            note=entry.note,
            recorded_at=timestamp,
        )

    def list_case(self, *, tenant_id: str, case_id: str) -> list[StoredLabourEntry]:
        if not tenant_id.strip() or not case_id.strip():
            raise ValueError("tenant_id and case_id are required")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT entry_id, tenant_id, case_id, activity, hours, note, recorded_at
                FROM cloud_switching_labour_entries
                WHERE tenant_id=? AND case_id=?
                ORDER BY entry_id ASC
                """,
                (tenant_id, case_id),
            ).fetchall()
        return [
            StoredLabourEntry(
                entry_id=int(row["entry_id"]),
                tenant_id=row["tenant_id"],
                case_id=row["case_id"],
                activity=ActivityCode(row["activity"]),
                hours=Decimal(row["hours"]),
                note=row["note"],
                recorded_at=datetime.fromisoformat(row["recorded_at"]),
            )
            for row in rows
        ]

    def summarize_case(self, *, tenant_id: str, case_id: str, revenue: Decimal | None = None) -> LabourSummary:
        records = self.list_case(tenant_id=tenant_id, case_id=case_id)
        entries = [
            LabourEntry(
                activity=record.activity,
                hours=record.hours,
                case_id=record.case_id,
                note=record.note,
            )
            for record in records
        ]
        return summarize_labour(entries, revenue=revenue)
