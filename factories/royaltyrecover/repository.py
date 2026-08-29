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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


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
            (_id("evt"), org_id, actor_id, event_type, entity_type, entity_id, _now(), json.dumps(payload or {}, sort_keys=True)),
        )

    def ensure_organization(self, org_id: str, name: str, actor_id: str = "system") -> dict[str, Any]:
        if not org_id or not name.strip():
            raise ValueError("organization id and name are required")
        row = self.conn.execute("SELECT * FROM organizations WHERE id=?", (org_id,)).fetchone()
        if row:
            if row["name"] != name:
                raise ScopeError("organization identifier already exists with a different name")
            return dict(row)
        self.conn.execute("INSERT INTO organizations(id, name, created_at) VALUES(?,?,?)", (org_id, name.strip(), _now()))
        self._audit(org_id, actor_id, "CREATE", "Organization", org_id)
        self.conn.commit()
        return dict(self.conn.execute("SELECT * FROM organizations WHERE id=?", (org_id,)).fetchone())

    def create_licensor(self, org_id: str, legal_name: str, actor_id: str) -> dict[str, Any]:
        self._require_org(org_id)
        licensor_id = _id("licensor")
        self.conn.execute("INSERT INTO licensors(id, organization_id, legal_name) VALUES(?,?,?)", (licensor_id, org_id, legal_name.strip()))
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
        licensee_id = _id("licensee")
        self.conn.execute("INSERT INTO licensees(id, organization_id, legal_name) VALUES(?,?,?)", (licensee_id, org_id, legal_name.strip()))
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
        agreement_id = _id("agreement")
        self.conn.execute(
            "INSERT INTO agreements(id, licensor_id, licensee_id, title, governing_law, status) VALUES(?,?,?,?,?, 'ACTIVE')",
            (agreement_id, licensor_id, licensee_id, title.strip(), governing_law),
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
        digest = sha256_bytes(content)
        version_id = _id("version")
        self.conn.execute(
            """INSERT INTO agreement_versions(id, agreement_id, version_label, effective_from, effective_to, document_sha256, source_uri)
               VALUES(?,?,?,?,?,?,?)""",
            (version_id, agreement_id, version_label.strip(), effective_from, effective_to, digest, source_uri),
        )
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

    def list_audit_events(self, org_id: str) -> list[dict[str, Any]]:
        self._require_org(org_id)
        return [dict(row) for row in self.conn.execute("SELECT * FROM audit_events WHERE organization_id=? ORDER BY event_at, id", (org_id,)).fetchall()]

    def _require_org(self, org_id: str) -> None:
        if not self.conn.execute("SELECT 1 FROM organizations WHERE id=?", (org_id,)).fetchone():
            raise NotFoundError("organization not found")
