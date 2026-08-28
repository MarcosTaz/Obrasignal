from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .ledger import LedgerKind, LedgerRecord, reconcile_ledger


class PayloadError(ValueError):
    pass


def _decimal(value, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise PayloadError(f"invalid {field}") from None
    if not parsed.is_finite() or parsed < 0:
        raise PayloadError(f"invalid {field}")
    return parsed


def _due(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise PayloadError("due must be true, false, or null")


def _bool(value, field: str) -> bool:
    if isinstance(value, bool):
        return value
    raise PayloadError(f"{field} must be boolean")


def reconcile_payload(rows: object, *, tenant_id: str) -> dict:
    if not tenant_id:
        raise PayloadError("tenant_id required")
    if not isinstance(rows, list):
        raise PayloadError("records_array_required")

    records: list[LedgerRecord] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise PayloadError(f"record {index} must be an object")
        if "tenant_id" in row:
            raise PayloadError("tenant_id_is_server_controlled")
        try:
            kind = LedgerKind(str(row.get("kind") or "").upper())
        except ValueError:
            raise PayloadError(f"record {index} has invalid kind") from None

        record = LedgerRecord(
            record_id=str(row.get("record_id") or "").strip(),
            tenant_id=tenant_id,
            customer_id=str(row.get("customer_id") or "").strip(),
            project_id=str(row.get("project_id") or "").strip(),
            currency=str(row.get("currency") or "").strip().upper(),
            kind=kind,
            amount=_decimal(row.get("amount"), "amount"),
            relates_to=str(row.get("relates_to") or "").strip() or None,
            verified=_bool(row.get("verified", False), "verified"),
            due=_due(row.get("due")),
        )
        if not all((record.record_id, record.customer_id, record.project_id, record.currency)):
            raise PayloadError(f"record {index} missing required scope field")
        records.append(record)

    result = reconcile_ledger(tuple(records))
    return {
        "tenant_id": tenant_id,
        "verified_cash": str(result.verified_cash),
        "due_unpaid": str(result.due_unpaid),
        "not_yet_due": str(result.not_yet_due),
        "unknown_value": str(result.unknown_value),
        "p0_count": result.p0_count,
        "positions": [
            {
                "invoice_id": p.invoice_id,
                "amount": str(p.amount),
                "verified_cash": str(p.verified_cash),
                "open_balance": str(p.open_balance),
                "due_unpaid": str(p.due_unpaid),
                "not_yet_due": str(p.not_yet_due),
                "unknown": p.unknown,
                "evidence_chain": list(p.evidence_chain),
            }
            for p in result.positions
        ],
        "anomalies": [
            {
                "code": a.code,
                "severity": a.severity.value,
                "record_id": a.record_id,
                "related_record_id": a.related_record_id,
                "detail": a.detail,
            }
            for a in result.anomalies
        ],
    }
