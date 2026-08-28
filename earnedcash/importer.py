from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import StringIO

from .ledger import LedgerKind, LedgerRecord


REQUIRED_COLUMNS = {
    "record_id",
    "tenant_id",
    "customer_id",
    "project_id",
    "currency",
    "kind",
    "amount",
    "verified",
}


@dataclass(frozen=True)
class ImportIssue:
    row: int
    code: str
    detail: str


@dataclass(frozen=True)
class ImportResult:
    records: tuple[LedgerRecord, ...]
    issues: tuple[ImportIssue, ...]
    rejected: bool


def _parse_bool(value: str) -> bool:
    raw = (value or "").strip().lower()
    if raw in {"true", "1", "yes", "y"}:
        return True
    if raw in {"false", "0", "no", "n", ""}:
        return False
    raise ValueError("invalid boolean")


def _parse_due(value: str) -> bool | None:
    raw = (value or "").strip().lower()
    if raw in {"", "unknown", "null", "none"}:
        return None
    return _parse_bool(raw)


def parse_ledger_csv(text: str, *, expected_tenant_id: str) -> ImportResult:
    if not expected_tenant_id:
        raise ValueError("expected_tenant_id is required")

    reader = csv.DictReader(StringIO(text))
    fields = set(reader.fieldnames or [])
    missing = sorted(REQUIRED_COLUMNS - fields)
    if missing:
        return ImportResult(
            records=(),
            issues=(
                ImportIssue(row=1, code="MISSING_COLUMNS", detail=",".join(missing)),
            ),
            rejected=True,
        )

    records: list[LedgerRecord] = []
    issues: list[ImportIssue] = []

    for row_number, row in enumerate(reader, start=2):
        try:
            tenant_id = (row.get("tenant_id") or "").strip()
            if tenant_id != expected_tenant_id:
                issues.append(
                    ImportIssue(
                        row=row_number,
                        code="TENANT_MISMATCH",
                        detail="row tenant does not match import tenant",
                    )
                )
                continue

            kind = LedgerKind((row.get("kind") or "").strip().upper())
            amount = Decimal((row.get("amount") or "").strip())
            if not amount.is_finite() or amount < 0:
                raise ValueError("amount must be finite and non-negative")

            record = LedgerRecord(
                record_id=(row.get("record_id") or "").strip(),
                tenant_id=tenant_id,
                customer_id=(row.get("customer_id") or "").strip(),
                project_id=(row.get("project_id") or "").strip(),
                currency=(row.get("currency") or "").strip().upper(),
                kind=kind,
                amount=amount,
                relates_to=(row.get("relates_to") or "").strip() or None,
                verified=_parse_bool(row.get("verified") or ""),
                due=_parse_due(row.get("due") or ""),
            )
            if not all(
                (record.record_id, record.customer_id, record.project_id, record.currency)
            ):
                raise ValueError("required identity/scope field is blank")
            records.append(record)
        except (ValueError, InvalidOperation) as exc:
            issues.append(
                ImportIssue(row=row_number, code="INVALID_ROW", detail=str(exc))
            )

    # Tenant mismatch is a hard rejection: never silently create a partial
    # cross-tenant dataset.
    hard_reject = any(issue.code == "TENANT_MISMATCH" for issue in issues)
    return ImportResult(
        records=() if hard_reject else tuple(records),
        issues=tuple(issues),
        rejected=hard_reject,
    )
