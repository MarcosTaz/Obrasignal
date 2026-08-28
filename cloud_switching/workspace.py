from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Dict, Optional

from .service import DecisionPackage


class WorkspaceAccessError(PermissionError):
    pass


@dataclass(frozen=True)
class StoredDecisionPackage:
    tenant_id: str
    package_id: str
    payload: DecisionPackage
    content_hash: str
    version: int


class DecisionWorkspace:
    def __init__(self) -> None:
        self._records: Dict[tuple[str, str], StoredDecisionPackage] = {}

    @staticmethod
    def _hash(package: DecisionPackage) -> str:
        encoded = json.dumps(asdict(package), sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
        return sha256(encoded).hexdigest()

    def save(self, *, tenant_id: str, package_id: str, package: DecisionPackage) -> StoredDecisionPackage:
        if not tenant_id.strip() or not package_id.strip():
            raise ValueError("tenant_id and package_id are required")
        if package.company_id != tenant_id:
            raise WorkspaceAccessError("decision package company does not match tenant")
        key = (tenant_id, package_id)
        previous = self._records.get(key)
        record = StoredDecisionPackage(
            tenant_id=tenant_id,
            package_id=package_id,
            payload=package,
            content_hash=self._hash(package),
            version=1 if previous is None else previous.version + 1,
        )
        self._records[key] = record
        return record

    def load(self, *, tenant_id: str, package_id: str) -> Optional[StoredDecisionPackage]:
        if not tenant_id.strip() or not package_id.strip():
            raise ValueError("tenant_id and package_id are required")
        return self._records.get((tenant_id, package_id))

    def require(self, *, tenant_id: str, package_id: str) -> StoredDecisionPackage:
        record = self.load(tenant_id=tenant_id, package_id=package_id)
        if record is None:
            raise KeyError("decision package not found for tenant")
        return record

    def backup(self, *, tenant_id: str) -> str:
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        records = [
            {
                "tenant_id": record.tenant_id,
                "package_id": record.package_id,
                "content_hash": record.content_hash,
                "version": record.version,
                "payload": asdict(record.payload),
            }
            for (record_tenant, _), record in sorted(self._records.items())
            if record_tenant == tenant_id
        ]
        return json.dumps({"tenant_id": tenant_id, "records": records}, sort_keys=True, default=str)
