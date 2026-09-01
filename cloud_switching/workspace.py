from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from hashlib import sha256
import json
from typing import Dict, Optional

from .decision import Decision
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

    @staticmethod
    def _optional_decimal(value):
        return None if value is None else Decimal(str(value))

    @classmethod
    def _package_from_dict(cls, payload: dict) -> DecisionPackage:
        return DecisionPackage(
            company_id=str(payload["company_id"]),
            case_id=str(payload["case_id"]),
            decision=Decision(payload["decision"]),
            reason=str(payload["reason"]),
            baseline_annual_cost=cls._optional_decimal(payload.get("baseline_annual_cost")),
            gross_switching_cost=cls._optional_decimal(payload.get("gross_switching_cost")),
            captured_incentives=Decimal(str(payload["captured_incentives"])),
            customer_cash_switching_cost=cls._optional_decimal(payload.get("customer_cash_switching_cost")),
            annual_status_quo_avoidance=cls._optional_decimal(payload.get("annual_status_quo_avoidance")),
            economic_payback_months=cls._optional_decimal(payload.get("economic_payback_months")),
            customer_cash_payback_months=cls._optional_decimal(payload.get("customer_cash_payback_months")),
            unresolved_material_inputs=tuple(payload.get("unresolved_material_inputs", ())),
            audit_evidence_ids=tuple(payload.get("audit_evidence_ids", ())),
        )

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

    def restore(self, *, tenant_id: str, backup_json: str) -> int:
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        document = json.loads(backup_json)
        if document.get("tenant_id") != tenant_id:
            raise WorkspaceAccessError("backup tenant does not match restore tenant")

        restored: Dict[tuple[str, str], StoredDecisionPackage] = {}
        for item in document.get("records", []):
            if item.get("tenant_id") != tenant_id:
                raise WorkspaceAccessError("backup contains cross-tenant record")
            package = self._package_from_dict(item["payload"])
            if package.company_id != tenant_id:
                raise WorkspaceAccessError("backup package company does not match tenant")
            expected_hash = str(item["content_hash"])
            actual_hash = self._hash(package)
            if actual_hash != expected_hash:
                raise ValueError("backup content hash mismatch")
            package_id = str(item["package_id"])
            key = (tenant_id, package_id)
            if key in restored:
                raise ValueError("duplicate package in backup")
            restored[key] = StoredDecisionPackage(
                tenant_id=tenant_id,
                package_id=package_id,
                payload=package,
                content_hash=actual_hash,
                version=int(item["version"]),
            )

        for key, record in restored.items():
            self._records[key] = record
        return len(restored)
