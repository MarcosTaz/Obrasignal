from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class ScopeError(PermissionError):
    pass


class NotFoundError(LookupError):
    pass


class ConflictError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _required_text(value: str, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def sha256_bytes(content: bytes) -> str:
    if not isinstance(content, bytes):
        raise TypeError("content must be bytes")
    return hashlib.sha256(content).hexdigest()


def canonical_input_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256_bytes(encoded)


class RoyaltyRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.conn = connection
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def memory(cls) -> "RoyaltyRepository":
        conn = sqlite3.connect(":memory:")
        repo = cls(conn)
        repo.initialize()
        return repo

    @classmethod
    def file(cls, path: str) -> "RoyaltyRepository":
        conn = sqlite3.connect(path)
        repo = cls(conn)
        repo.initialize()
        return repo

    def initialize(self) -> None:
        self.conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _audit(self, org_id: str, actor_id: str, event_type: str, entity_type: str, entity_id: str, payload: Optional[dict[str, Any]] = None) -> None:
        self.conn.execute(
            "INSERT INTO audit_events(id, organization_id, actor_id, event_type, entity_type, entity_id, event_at, payload_json) VALUES(?,?,?,?,?,?,?,?)",
            (_id("evt"), org_id, _required_text(actor_id, "actor_id"), event_type, entity_type, entity_id, _now(), json.dumps(payload or {}, sort_keys=True)),
        )

    def ensure_organization(self, org_id: str, name: str, actor_id: str = "system") -> dict[str, Any]:
        org_id = _required_text(org_id, "organization_id")
        name = _required_text(name, "organization name")
        row = self.conn.execute("SELECT * FROM organizations WHERE id=?", (org_id,)).fetchone()
        if row:
            if row["name"] != name:
                raise ScopeError("organization identifier already exists with a different name")
            return dict(row)
        self.conn.execute("INSERT INTO organizations(id, name, created_at) VALUES(?,?,?)", (org_id, name, _now()))
        self._audit(org_id, actor_id, "CREATE", "Organization", org_id)
        self.conn.commit()
        return dict(self.conn.execute("SELECT * FROM organizations WHERE id=?", (org_id,)).fetchone())

    def create_licensor(self, org_id: str, legal_name: str, actor_id: str) -> dict[str, Any]:
        self._require_org(org_id)
        legal_name = _required_text(legal_name, "legal_name")
        licensor_id = _id("licensor")
        self.conn.execute("INSERT INTO licensors(id, organization_id, legal_name) VALUES(?,?,?)", (licensor_id, org_id, legal_name))
        self._audit(org_id, actor_id, "CREATE", "Licensor", licensor_id)
        self.conn.commit()
        return self.get_licensor(org_id, licensor_id)

    def get_licensor(self, org_id: str, licensor_id: str) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM licensors WHERE id=? AND organization_id=?", (licensor_id, org_id)).fetchone()
        if not row:
            raise NotFoundError("licensor not found in organization scope")
        return dict(row)

    def create_licensee(self, org_id: str, legal_name: str, actor_id: str) -> dict[str, Any]:
        self._require_org(org_id)
        legal_name = _required_text(legal_name, "legal_name")
        licensee_id = _id("licensee")
        self.conn.execute("INSERT INTO licensees(id, organization_id, legal_name) VALUES(?,?,?)", (licensee_id, org_id, legal_name))
        self._audit(org_id, actor_id, "CREATE", "Licensee", licensee_id)
        self.conn.commit()
        return self.get_licensee(org_id, licensee_id)

    def get_licensee(self, org_id: str, licensee_id: str) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM licensees WHERE id=? AND organization_id=?", (licensee_id, org_id)).fetchone()
        if not row:
            raise NotFoundError("licensee not found in organization scope")
        return dict(row)

    def create_agreement(self, org_id: str, licensor_id: str, licensee_id: str, title: str, actor_id: str, governing_law: Optional[str] = None) -> dict[str, Any]:
        self.get_licensor(org_id, licensor_id)
        self.get_licensee(org_id, licensee_id)
        title = _required_text(title, "title")
        agreement_id = _id("agreement")
        self.conn.execute(
            "INSERT INTO agreements(id, licensor_id, licensee_id, title, governing_law, status) VALUES(?,?,?,?,?, 'ACTIVE')",
            (agreement_id, licensor_id, licensee_id, title, governing_law),
        )
        self._audit(org_id, actor_id, "CREATE", "Agreement", agreement_id)
        self.conn.commit()
        return self.get_agreement(org_id, agreement_id)

    def get_agreement(self, org_id: str, agreement_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            """SELECT a.* FROM agreements a
               JOIN licensors l ON l.id=a.licensor_id
               JOIN licensees e ON e.id=a.licensee_id
               WHERE a.id=? AND l.organization_id=? AND e.organization_id=?""",
            (agreement_id, org_id, org_id),
        ).fetchone()
        if not row:
            raise NotFoundError("agreement not found in organization scope")
        return dict(row)

    def add_agreement_version(self, org_id: str, agreement_id: str, version_label: str, content: bytes, actor_id: str, effective_from: Optional[str] = None, effective_to: Optional[str] = None, source_uri: Optional[str] = None) -> dict[str, Any]:
        self.get_agreement(org_id, agreement_id)
        version_label = _required_text(version_label, "version_label")
        digest = sha256_bytes(content)
        version_id = _id("version")
        try:
            self.conn.execute(
                """INSERT INTO agreement_versions(id, agreement_id, version_label, effective_from, effective_to, document_sha256, source_uri)
                   VALUES(?,?,?,?,?,?,?)""",
                (version_id, agreement_id, version_label, effective_from, effective_to, digest, source_uri),
            )
        except sqlite3.IntegrityError as exc:
            self.conn.rollback()
            raise ConflictError("agreement version label already exists or violates integrity constraints") from exc
        self._audit(org_id, actor_id, "CREATE", "AgreementVersion", version_id, {"agreement_id": agreement_id, "sha256": digest})
        self.conn.commit()
        return self.get_agreement_version(org_id, version_id)

    def get_agreement_version(self, org_id: str, version_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            """SELECT v.* FROM agreement_versions v
               JOIN agreements a ON a.id=v.agreement_id
               JOIN licensors l ON l.id=a.licensor_id
               JOIN licensees e ON e.id=a.licensee_id
               WHERE v.id=? AND l.organization_id=? AND e.organization_id=?""",
            (version_id, org_id, org_id),
        ).fetchone()
        if not row:
            raise NotFoundError("agreement version not found in organization scope")
        return dict(row)

    def add_evidence(self, org_id: str, evidence_type: str, content: bytes, actor_id: str, source_uri: Optional[str] = None, metadata: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        self._require_org(org_id)
        evidence_type = _required_text(evidence_type, "evidence_type")
        evidence_id = _id("evidence")
        digest = sha256_bytes(content)
        self.conn.execute(
            """INSERT INTO evidence(id, organization_id, evidence_type, source_uri, source_sha256, captured_at, metadata_json)
               VALUES(?,?,?,?,?,?,?)""",
            (evidence_id, org_id, evidence_type, source_uri, digest, _now(), json.dumps(metadata or {}, sort_keys=True)),
        )
        self._audit(org_id, actor_id, "CREATE", "Evidence", evidence_id, {"sha256": digest})
        self.conn.commit()
        return self.get_evidence(org_id, evidence_id)

    def get_evidence(self, org_id: str, evidence_id: str) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM evidence WHERE id=? AND organization_id=?", (evidence_id, org_id)).fetchone()
        if not row:
            raise NotFoundError("evidence not found in organization scope")
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
        return result

    def create_calculation_run(self, org_id: str, agreement_id: str, agreement_version_id: str, period_start: str, period_end: str, engine_version: str, input_payload: dict[str, Any], actor_id: str) -> dict[str, Any]:
        self.get_agreement(org_id, agreement_id)
        version = self.get_agreement_version(org_id, agreement_version_id)
        if version["agreement_id"] != agreement_id:
            raise ScopeError("agreement version does not belong to the supplied agreement")
        period_start = _required_text(period_start, "period_start")
        period_end = _required_text(period_end, "period_end")
        engine_version = _required_text(engine_version, "engine_version")
        if period_end < period_start:
            raise ValueError("period_end must not precede period_start")
        input_hash = canonical_input_hash(input_payload)
        run_id = _id("calc")
        self.conn.execute(
            """INSERT INTO calculation_runs(id, agreement_id, agreement_version_id, period_start, period_end, engine_version, input_hash, created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (run_id, agreement_id, agreement_version_id, period_start, period_end, engine_version, input_hash, _now()),
        )
        self._audit(org_id, actor_id, "CREATE", "CalculationRun", run_id, {"agreement_version_id": agreement_version_id, "input_hash": input_hash, "engine_version": engine_version})
        self.conn.commit()
        return self.get_calculation_run(org_id, run_id)

    def get_calculation_run(self, org_id: str, run_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            """SELECT r.* FROM calculation_runs r
               JOIN agreements a ON a.id=r.agreement_id
               JOIN licensors l ON l.id=a.licensor_id
               JOIN licensees e ON e.id=a.licensee_id
               WHERE r.id=? AND l.organization_id=? AND e.organization_id=?""",
            (run_id, org_id, org_id),
        ).fetchone()
        if not row:
            raise NotFoundError("calculation run not found in organization scope")
        return dict(row)

    def calculation_run_freshness(self, org_id: str, run_id: str, operative_agreement_version_id: str, current_engine_version: str, current_input_payload: dict[str, Any]) -> dict[str, Any]:
        run = self.get_calculation_run(org_id, run_id)
        operative = self.get_agreement_version(org_id, operative_agreement_version_id)
        if operative["agreement_id"] != run["agreement_id"]:
            raise ScopeError("operative agreement version belongs to a different agreement")
        current_hash = canonical_input_hash(current_input_payload)
        reasons = []
        if run["agreement_version_id"] != operative_agreement_version_id:
            reasons.append("AGREEMENT_VERSION_CHANGED")
        if run["engine_version"] != current_engine_version:
            reasons.append("ENGINE_VERSION_CHANGED")
        if run["input_hash"] != current_hash:
            reasons.append("INPUT_DATA_CHANGED")
        return {
            "run_id": run_id,
            "status": "STALE" if reasons else "CURRENT",
            "reasons": reasons,
            "stored_input_hash": run["input_hash"],
            "current_input_hash": current_hash,
        }

    def list_audit_events(self, org_id: str) -> list[dict[str, Any]]:
        self._require_org(org_id)
        return [dict(row) for row in self.conn.execute("SELECT * FROM audit_events WHERE organization_id=? ORDER BY event_at, id", (org_id,)).fetchall()]

    def _require_org(self, org_id: str) -> None:
        org_id = _required_text(org_id, "organization_id")
        if not self.conn.execute("SELECT 1 FROM organizations WHERE id=?", (org_id,)).fetchone():
            raise NotFoundError("organization not found")
