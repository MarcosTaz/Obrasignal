from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from factory_cloud.assurance_store import AssuranceStoreError


ALLOWED_NOTICE_STATES = {"UNKNOWN", "DECLARED_DATE_FOR_REVIEW", "DECLARED_NONE_FOR_REVIEW"}
MAX_REFERENCE_CHARS = 512
MAX_FINDING_ID_CHARS = 2_048
MAX_TENANT_CHARS = 64
MAX_MISSING_EVIDENCE_ITEMS = 100
MAX_MISSING_EVIDENCE_CHARS = 128
_TENANT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


@dataclass(frozen=True)
class IndustrialCaseMetadata:
    finding_id: str
    tenant_id: str
    claim_family: str
    customer_ref: str
    program_ref: str
    event_ref: str
    entitlement_id: str
    deadline_id: str
    recovery_fingerprint: str
    notice_deadline_state: str
    missing_evidence: tuple[str, ...]


class IndustrialClaimsCaseStore:
    """Durable Industrial-specific metadata needed to resume assisted cases.

    The store contains identifiers and truth-state metadata only; documentary
    content remains outside this table and is represented by immutable hashes in
    the shared evidence store.
    """

    def __init__(self, database: str | Path):
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS industrial_claim_cases(
                    finding_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    claim_family TEXT NOT NULL,
                    customer_ref TEXT NOT NULL,
                    program_ref TEXT NOT NULL,
                    event_ref TEXT NOT NULL,
                    entitlement_id TEXT NOT NULL,
                    deadline_id TEXT NOT NULL,
                    recovery_fingerprint TEXT NOT NULL,
                    notice_deadline_state TEXT NOT NULL,
                    missing_evidence_json TEXT NOT NULL
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_industrial_claim_cases_tenant ON industrial_claim_cases(tenant_id,finding_id)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _has_forbidden_controls(text: str) -> bool:
        return any(ord(char) < 32 or ord(char) == 127 for char in text)

    @classmethod
    def _required(cls, value: object, *, label: str, max_chars: int) -> str:
        raw = str(value or "")
        if cls._has_forbidden_controls(raw):
            raise AssuranceStoreError(f"industrial case {label} is invalid")
        text = raw.strip()
        if not text or len(text) > max_chars:
            raise AssuranceStoreError(f"industrial case {label} is invalid")
        return text

    @classmethod
    def _tenant(cls, value: object) -> str:
        tenant = cls._required(value, label="tenant_id", max_chars=MAX_TENANT_CHARS)
        if not _TENANT_RE.fullmatch(tenant):
            raise AssuranceStoreError("industrial case tenant_id is invalid")
        return tenant

    @classmethod
    def _validate(cls, item: IndustrialCaseMetadata) -> IndustrialCaseMetadata:
        missing_items: list[str] = []
        for value in item.missing_evidence:
            raw = str(value)
            if cls._has_forbidden_controls(raw):
                raise AssuranceStoreError("industrial case missing-evidence lineage is invalid")
            text = raw.strip()
            if text:
                missing_items.append(text)
        missing = tuple(missing_items)
        if len(missing) > MAX_MISSING_EVIDENCE_ITEMS or any(len(value) > MAX_MISSING_EVIDENCE_CHARS for value in missing):
            raise AssuranceStoreError("industrial case missing-evidence lineage is invalid")
        notice_state = str(item.notice_deadline_state).strip()
        if notice_state not in ALLOWED_NOTICE_STATES:
            raise AssuranceStoreError("industrial case notice truth state is invalid")
        return IndustrialCaseMetadata(
            finding_id=cls._required(item.finding_id, label="finding_id", max_chars=MAX_FINDING_ID_CHARS),
            tenant_id=cls._tenant(item.tenant_id),
            claim_family=cls._required(item.claim_family, label="claim_family", max_chars=128),
            customer_ref=cls._required(item.customer_ref, label="customer_ref", max_chars=MAX_REFERENCE_CHARS),
            program_ref=cls._required(item.program_ref, label="program_ref", max_chars=MAX_REFERENCE_CHARS),
            event_ref=cls._required(item.event_ref, label="event_ref", max_chars=MAX_REFERENCE_CHARS),
            entitlement_id=cls._required(item.entitlement_id, label="entitlement_id", max_chars=MAX_FINDING_ID_CHARS),
            deadline_id=cls._required(item.deadline_id, label="deadline_id", max_chars=MAX_FINDING_ID_CHARS),
            recovery_fingerprint=cls._required(item.recovery_fingerprint, label="recovery_fingerprint", max_chars=256),
            notice_deadline_state=notice_state,
            missing_evidence=missing,
        )

    @classmethod
    def _values(cls, item: IndustrialCaseMetadata) -> tuple[str, ...]:
        valid = cls._validate(item)
        return (
            valid.finding_id, valid.tenant_id, valid.claim_family, valid.customer_ref, valid.program_ref, valid.event_ref,
            valid.entitlement_id, valid.deadline_id, valid.recovery_fingerprint, valid.notice_deadline_state,
            json.dumps(list(valid.missing_evidence), sort_keys=True, separators=(",", ":")),
        )

    def _put(self, conn: sqlite3.Connection, item: IndustrialCaseMetadata) -> None:
        values = self._values(item)
        existing = conn.execute("SELECT * FROM industrial_claim_cases WHERE finding_id=?", (values[0],)).fetchone()
        if existing is not None:
            keys = (
                "finding_id", "tenant_id", "claim_family", "customer_ref", "program_ref", "event_ref",
                "entitlement_id", "deadline_id", "recovery_fingerprint", "notice_deadline_state", "missing_evidence_json",
            )
            current = tuple(str(existing[key]) for key in keys)
            if current != values:
                raise AssuranceStoreError("immutable industrial case metadata collision")
            return
        conn.execute("INSERT INTO industrial_claim_cases VALUES(?,?,?,?,?,?,?,?,?,?,?)", values)

    def put(self, item: IndustrialCaseMetadata, *, connection: sqlite3.Connection | None = None) -> None:
        if connection is not None:
            self._put(connection, item)
            return
        with self._connect() as conn:
            self._put(conn, item)

    def get(self, *, tenant_id: str, finding_id: str) -> IndustrialCaseMetadata:
        tenant = self._tenant(tenant_id)
        finding = self._required(finding_id, label="finding_id", max_chars=MAX_FINDING_ID_CHARS)
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM industrial_claim_cases WHERE tenant_id=? AND finding_id=?", (tenant, finding)).fetchone()
        if row is None:
            raise AssuranceStoreError("tenant-scoped industrial case metadata not found")
        try:
            missing = json.loads(row["missing_evidence_json"])
        except (TypeError, ValueError) as exc:
            raise AssuranceStoreError("industrial case missing-evidence lineage is invalid") from exc
        if not isinstance(missing, list):
            raise AssuranceStoreError("industrial case missing-evidence lineage is invalid")
        return self._validate(IndustrialCaseMetadata(
            finding_id=str(row["finding_id"]), tenant_id=str(row["tenant_id"]), claim_family=str(row["claim_family"]),
            customer_ref=str(row["customer_ref"]), program_ref=str(row["program_ref"]), event_ref=str(row["event_ref"]),
            entitlement_id=str(row["entitlement_id"]), deadline_id=str(row["deadline_id"]),
            recovery_fingerprint=str(row["recovery_fingerprint"]), notice_deadline_state=str(row["notice_deadline_state"]),
            missing_evidence=tuple(str(item) for item in missing),
        ))

    def count(self, tenant_id: str) -> int:
        tenant = self._tenant(tenant_id)
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM industrial_claim_cases WHERE tenant_id=?", (tenant,)).fetchone()
        return int(row["n"])
