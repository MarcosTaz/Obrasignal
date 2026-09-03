from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from factory_cloud.assurance_store import AssuranceStoreError


MAX_TENANT_CHARS = 64
MAX_FINDING_ID_CHARS = 2_048
MAX_FINGERPRINT_CHARS = 256
_TENANT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


@dataclass(frozen=True)
class IndustrialCaseRevision:
    finding_id: str
    tenant_id: str
    recovery_fingerprint: str
    revision: int
    supersedes_finding_id: str | None
    is_current: bool


class IndustrialClaimsRevisionStore:
    """Durable revision lineage for one logical recovery fingerprint.

    A revision changes documentary/economic reconstruction while preserving the
    same duplicate-prevention fingerprint. Exactly one revision may be current.
    Historical findings remain immutable but cannot be advanced once superseded.
    """

    def __init__(self, database: str | Path):
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS industrial_claim_revisions(
                    finding_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    recovery_fingerprint TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    supersedes_finding_id TEXT,
                    is_current INTEGER NOT NULL CHECK(is_current IN (0,1)),
                    UNIQUE(tenant_id,recovery_fingerprint,revision)
                );
                CREATE INDEX IF NOT EXISTS idx_industrial_revision_tenant
                    ON industrial_claim_revisions(tenant_id,finding_id);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_industrial_revision_one_current
                    ON industrial_claim_revisions(tenant_id,recovery_fingerprint)
                    WHERE is_current=1;
                """
            )
            self._backfill_existing_cases(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _has_controls(text: str) -> bool:
        return any(ord(char) < 32 or ord(char) == 127 for char in text)

    @classmethod
    def _required(cls, value: object, *, label: str, max_chars: int) -> str:
        raw = str(value or "")
        if cls._has_controls(raw):
            raise AssuranceStoreError(f"industrial revision {label} is invalid")
        text = raw.strip()
        if not text or len(text) > max_chars:
            raise AssuranceStoreError(f"industrial revision {label} is invalid")
        return text

    @classmethod
    def _tenant(cls, value: object) -> str:
        tenant = cls._required(value, label="tenant_id", max_chars=MAX_TENANT_CHARS)
        if not _TENANT_RE.fullmatch(tenant):
            raise AssuranceStoreError("industrial revision tenant_id is invalid")
        return tenant

    @classmethod
    def _validated(cls, item: IndustrialCaseRevision) -> IndustrialCaseRevision:
        tenant = cls._tenant(item.tenant_id)
        finding = cls._required(item.finding_id, label="finding_id", max_chars=MAX_FINDING_ID_CHARS)
        fingerprint = cls._required(item.recovery_fingerprint, label="recovery_fingerprint", max_chars=MAX_FINGERPRINT_CHARS)
        if not isinstance(item.revision, int) or isinstance(item.revision, bool) or item.revision < 1:
            raise AssuranceStoreError("industrial revision number is invalid")
        supersedes = None
        if item.supersedes_finding_id is not None:
            supersedes = cls._required(item.supersedes_finding_id, label="supersedes_finding_id", max_chars=MAX_FINDING_ID_CHARS)
            if supersedes == finding:
                raise AssuranceStoreError("industrial revision cannot supersede itself")
        if item.revision == 1 and supersedes is not None:
            raise AssuranceStoreError("initial industrial revision cannot supersede another finding")
        if item.revision > 1 and supersedes is None:
            raise AssuranceStoreError("amended industrial revision requires superseded finding")
        if not isinstance(item.is_current, bool):
            raise AssuranceStoreError("industrial revision current flag is invalid")
        return IndustrialCaseRevision(finding, tenant, fingerprint, item.revision, supersedes, item.is_current)

    @staticmethod
    def _from_row(row: sqlite3.Row) -> IndustrialCaseRevision:
        return IndustrialCaseRevision(
            finding_id=str(row["finding_id"]),
            tenant_id=str(row["tenant_id"]),
            recovery_fingerprint=str(row["recovery_fingerprint"]),
            revision=int(row["revision"]),
            supersedes_finding_id=str(row["supersedes_finding_id"]) if row["supersedes_finding_id"] is not None else None,
            is_current=bool(row["is_current"]),
        )

    def _validate_lineage(self, conn: sqlite3.Connection, item: IndustrialCaseRevision) -> IndustrialCaseRevision:
        record = self._validated(item)
        original = record
        visited = {record.finding_id}
        while record.revision > 1:
            predecessor_id = record.supersedes_finding_id
            if predecessor_id is None:
                raise AssuranceStoreError("industrial revision predecessor is missing")
            predecessor_row = conn.execute(
                "SELECT * FROM industrial_claim_revisions WHERE tenant_id=? AND finding_id=?",
                (record.tenant_id, predecessor_id),
            ).fetchone()
            if predecessor_row is None:
                raise AssuranceStoreError("industrial revision predecessor is missing")
            predecessor = self._validated(self._from_row(predecessor_row))
            if predecessor.finding_id in visited:
                raise AssuranceStoreError("industrial revision lineage contains a cycle")
            visited.add(predecessor.finding_id)
            if predecessor.recovery_fingerprint != original.recovery_fingerprint:
                raise AssuranceStoreError("industrial revision predecessor fingerprint is inconsistent")
            if predecessor.revision != record.revision - 1:
                raise AssuranceStoreError("industrial revision predecessor chronology is invalid")
            if predecessor.is_current:
                raise AssuranceStoreError("industrial revision predecessor cannot be current")
            record = predecessor
        return original

    def _backfill_existing_cases(self, conn: sqlite3.Connection) -> None:
        table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='industrial_claim_cases'"
        ).fetchone()
        if table is None:
            return
        rows = conn.execute(
            """SELECT finding_id,tenant_id,recovery_fingerprint
               FROM industrial_claim_cases
               ORDER BY tenant_id,recovery_fingerprint,finding_id"""
        ).fetchall()
        grouped: dict[tuple[str, str], list[sqlite3.Row]] = {}
        for row in rows:
            key = (str(row["tenant_id"]), str(row["recovery_fingerprint"]))
            grouped.setdefault(key, []).append(row)
        for (tenant, fingerprint), cases in grouped.items():
            existing = conn.execute(
                "SELECT COUNT(*) AS n FROM industrial_claim_revisions WHERE tenant_id=? AND recovery_fingerprint=?",
                (tenant, fingerprint),
            ).fetchone()
            if int(existing["n"]) > 0:
                continue
            if len(cases) != 1:
                raise AssuranceStoreError("ambiguous pre-revision industrial case lineage")
            initial = IndustrialCaseRevision(
                finding_id=str(cases[0]["finding_id"]),
                tenant_id=tenant,
                recovery_fingerprint=fingerprint,
                revision=1,
                supersedes_finding_id=None,
                is_current=True,
            )
            self._register_initial(conn, self._validated(initial))

    def register_initial(self, item: IndustrialCaseRevision, *, connection: sqlite3.Connection | None = None) -> IndustrialCaseRevision:
        valid = self._validated(item)
        if valid.revision != 1 or valid.supersedes_finding_id is not None or not valid.is_current:
            raise AssuranceStoreError("initial industrial revision contract is invalid")
        if connection is not None:
            return self._register_initial(connection, valid)
        with self._connect() as conn:
            return self._register_initial(conn, valid)

    def _register_initial(self, conn: sqlite3.Connection, item: IndustrialCaseRevision) -> IndustrialCaseRevision:
        existing = conn.execute("SELECT * FROM industrial_claim_revisions WHERE finding_id=?", (item.finding_id,)).fetchone()
        if existing is not None:
            current = self._validated(self._from_row(existing))
            if current != item:
                raise AssuranceStoreError("immutable industrial revision collision")
            return current
        competing = conn.execute(
            "SELECT finding_id FROM industrial_claim_revisions WHERE tenant_id=? AND recovery_fingerprint=? AND is_current=1",
            (item.tenant_id, item.recovery_fingerprint),
        ).fetchone()
        if competing is not None:
            raise AssuranceStoreError("industrial recovery fingerprint already has a current revision")
        conn.execute(
            "INSERT INTO industrial_claim_revisions VALUES(?,?,?,?,?,?)",
            (item.finding_id, item.tenant_id, item.recovery_fingerprint, 1, None, 1),
        )
        return item

    def supersede(
        self,
        *,
        tenant_id: str,
        recovery_fingerprint: str,
        current_finding_id: str,
        new_finding_id: str,
        connection: sqlite3.Connection | None = None,
    ) -> IndustrialCaseRevision:
        tenant = self._tenant(tenant_id)
        fingerprint = self._required(recovery_fingerprint, label="recovery_fingerprint", max_chars=MAX_FINGERPRINT_CHARS)
        current_key = self._required(current_finding_id, label="current_finding_id", max_chars=MAX_FINDING_ID_CHARS)
        new_key = self._required(new_finding_id, label="new_finding_id", max_chars=MAX_FINDING_ID_CHARS)
        if current_key == new_key:
            raise AssuranceStoreError("industrial amendment requires a new finding id")
        if connection is not None:
            return self._supersede(connection, tenant, fingerprint, current_key, new_key)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            record = self._supersede(conn, tenant, fingerprint, current_key, new_key)
            conn.commit()
            return record

    def _supersede(self, conn: sqlite3.Connection, tenant: str, fingerprint: str, current_key: str, new_key: str) -> IndustrialCaseRevision:
        current = conn.execute(
            "SELECT * FROM industrial_claim_revisions WHERE tenant_id=? AND recovery_fingerprint=? AND is_current=1",
            (tenant, fingerprint),
        ).fetchone()
        if current is None:
            raise AssuranceStoreError("current industrial revision not found")
        current_record = self._validate_lineage(conn, self._from_row(current))
        if current_record.finding_id != current_key:
            raise AssuranceStoreError("industrial amendment target is not the current revision")
        existing_new = conn.execute("SELECT * FROM industrial_claim_revisions WHERE finding_id=?", (new_key,)).fetchone()
        if existing_new is not None:
            raise AssuranceStoreError("industrial amendment finding id already exists")
        next_revision = current_record.revision + 1
        conn.execute("UPDATE industrial_claim_revisions SET is_current=0 WHERE finding_id=?", (current_key,))
        conn.execute(
            "INSERT INTO industrial_claim_revisions VALUES(?,?,?,?,?,?)",
            (new_key, tenant, fingerprint, next_revision, current_key, 1),
        )
        return IndustrialCaseRevision(new_key, tenant, fingerprint, next_revision, current_key, True)

    def get(self, *, tenant_id: str, finding_id: str) -> IndustrialCaseRevision:
        tenant = self._tenant(tenant_id)
        finding = self._required(finding_id, label="finding_id", max_chars=MAX_FINDING_ID_CHARS)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM industrial_claim_revisions WHERE tenant_id=? AND finding_id=?",
                (tenant, finding),
            ).fetchone()
            if row is None:
                raise AssuranceStoreError("tenant-scoped industrial revision not found")
            return self._validate_lineage(conn, self._from_row(row))

    def require_current(self, *, tenant_id: str, finding_id: str) -> IndustrialCaseRevision:
        record = self.get(tenant_id=tenant_id, finding_id=finding_id)
        if not record.is_current:
            raise AssuranceStoreError("industrial finding has been superseded by a newer revision")
        return record

    def current_for_fingerprint(self, *, tenant_id: str, recovery_fingerprint: str) -> IndustrialCaseRevision:
        tenant = self._tenant(tenant_id)
        fingerprint = self._required(recovery_fingerprint, label="recovery_fingerprint", max_chars=MAX_FINGERPRINT_CHARS)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM industrial_claim_revisions WHERE tenant_id=? AND recovery_fingerprint=? AND is_current=1",
                (tenant, fingerprint),
            ).fetchall()
            if len(rows) != 1:
                raise AssuranceStoreError("industrial recovery fingerprint must have exactly one current revision")
            return self._validate_lineage(conn, self._from_row(rows[0]))

    def count(self, tenant_id: str) -> int:
        tenant = self._tenant(tenant_id)
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM industrial_claim_revisions WHERE tenant_id=?", (tenant,)).fetchone()
        return int(row["n"])
