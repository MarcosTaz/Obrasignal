from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import sqlite3
from pathlib import Path
from typing import Optional

from .service import DecisionPackage
from .workspace import DecisionWorkspace, StoredDecisionPackage, WorkspaceAccessError


@dataclass(frozen=True)
class StoredDelivery:
    tenant_id: str
    package_id: str
    payload: dict
    content_hash: str
    version: int


class SQLiteDecisionWorkspace:
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
                CREATE TABLE IF NOT EXISTS cloud_switching_decision_packages (
                    tenant_id TEXT NOT NULL,
                    package_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    PRIMARY KEY (tenant_id, package_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cloud_switching_deliveries (
                    tenant_id TEXT NOT NULL,
                    package_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    PRIMARY KEY (tenant_id, package_id)
                )
                """
            )

    @staticmethod
    def _serialize(package: DecisionPackage) -> str:
        return json.dumps(asdict(package), sort_keys=True, default=str, separators=(",", ":"))

    @staticmethod
    def _canonical_json(payload: dict) -> str:
        return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))

    @classmethod
    def _payload_hash(cls, payload: dict) -> str:
        return sha256(cls._canonical_json(payload).encode("utf-8")).hexdigest()

    @staticmethod
    def _next_version(connection: sqlite3.Connection, table: str, tenant_id: str, package_id: str) -> int:
        if table not in {"cloud_switching_decision_packages", "cloud_switching_deliveries"}:
            raise ValueError("unsupported workspace table")
        previous = connection.execute(
            f"SELECT version FROM {table} WHERE tenant_id=? AND package_id=?",
            (tenant_id, package_id),
        ).fetchone()
        return 1 if previous is None else int(previous["version"]) + 1

    def save(self, *, tenant_id: str, package_id: str, package: DecisionPackage) -> StoredDecisionPackage:
        if not tenant_id.strip() or not package_id.strip():
            raise ValueError("tenant_id and package_id are required")
        if package.company_id != tenant_id:
            raise WorkspaceAccessError("decision package company does not match tenant")
        content_hash = DecisionWorkspace._hash(package)
        payload_json = self._serialize(package)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            version = self._next_version(connection, "cloud_switching_decision_packages", tenant_id, package_id)
            connection.execute(
                """
                INSERT INTO cloud_switching_decision_packages
                    (tenant_id, package_id, payload_json, content_hash, version)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, package_id) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    content_hash=excluded.content_hash,
                    version=excluded.version
                """,
                (tenant_id, package_id, payload_json, content_hash, version),
            )
        return StoredDecisionPackage(tenant_id, package_id, package, content_hash, version)

    def load(self, *, tenant_id: str, package_id: str) -> Optional[StoredDecisionPackage]:
        if not tenant_id.strip() or not package_id.strip():
            raise ValueError("tenant_id and package_id are required")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT tenant_id, package_id, payload_json, content_hash, version
                FROM cloud_switching_decision_packages
                WHERE tenant_id=? AND package_id=?
                """,
                (tenant_id, package_id),
            ).fetchone()
        if row is None:
            return None
        package = DecisionWorkspace._package_from_dict(json.loads(row["payload_json"]))
        actual_hash = DecisionWorkspace._hash(package)
        if actual_hash != row["content_hash"]:
            raise ValueError("stored decision package content hash mismatch")
        if package.company_id != tenant_id:
            raise WorkspaceAccessError("stored package company does not match tenant")
        return StoredDecisionPackage(
            tenant_id=row["tenant_id"],
            package_id=row["package_id"],
            payload=package,
            content_hash=row["content_hash"],
            version=int(row["version"]),
        )

    def require(self, *, tenant_id: str, package_id: str) -> StoredDecisionPackage:
        record = self.load(tenant_id=tenant_id, package_id=package_id)
        if record is None:
            raise KeyError("decision package not found for tenant")
        return record

    def save_delivery(self, *, tenant_id: str, package_id: str, payload: dict) -> StoredDelivery:
        if not tenant_id.strip() or not package_id.strip():
            raise ValueError("tenant_id and package_id are required")
        payload_tenant = str(payload.get("decision", {}).get("company_id", ""))
        if payload_tenant != tenant_id:
            raise WorkspaceAccessError("delivery decision company does not match tenant")
        payload_json = self._canonical_json(payload)
        content_hash = self._payload_hash(payload)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            version = self._next_version(connection, "cloud_switching_deliveries", tenant_id, package_id)
            connection.execute(
                """
                INSERT INTO cloud_switching_deliveries
                    (tenant_id, package_id, payload_json, content_hash, version)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, package_id) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    content_hash=excluded.content_hash,
                    version=excluded.version
                """,
                (tenant_id, package_id, payload_json, content_hash, version),
            )
        return StoredDelivery(tenant_id, package_id, payload, content_hash, version)

    def load_delivery(self, *, tenant_id: str, package_id: str) -> Optional[StoredDelivery]:
        if not tenant_id.strip() or not package_id.strip():
            raise ValueError("tenant_id and package_id are required")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT tenant_id, package_id, payload_json, content_hash, version
                FROM cloud_switching_deliveries
                WHERE tenant_id=? AND package_id=?
                """,
                (tenant_id, package_id),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        if self._payload_hash(payload) != row["content_hash"]:
            raise ValueError("stored delivery content hash mismatch")
        if str(payload.get("decision", {}).get("company_id", "")) != tenant_id:
            raise WorkspaceAccessError("stored delivery company does not match tenant")
        return StoredDelivery(
            tenant_id=row["tenant_id"],
            package_id=row["package_id"],
            payload=payload,
            content_hash=row["content_hash"],
            version=int(row["version"]),
        )
