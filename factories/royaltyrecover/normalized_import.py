from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional

from repository import ConflictError, RoyaltyRepository


MAX_BATCH_ROWS = 10_000


@dataclass(frozen=True)
class NormalizedSalesRow:
    source_row_key: str
    transaction_date: str
    gross_amount: Optional[Decimal] = None
    units: Optional[Decimal] = None
    currency: Optional[str] = None


@dataclass(frozen=True)
class ImportResult:
    source_dataset_id: str
    source_system: str
    row_count: int
    dataset_sha256: str
    evidence_id: str


def _required(value: str, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _decimal(value: Optional[Decimal], field: str) -> Optional[str]:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if not parsed.is_finite():
        raise ValueError(f"{field} must be finite")
    return format(parsed, "f")


def _canonical_row(row: NormalizedSalesRow) -> dict[str, Any]:
    row_key = _required(row.source_row_key, "source_row_key")
    try:
        transaction_date = date.fromisoformat(_required(row.transaction_date, "transaction_date")).isoformat()
    except ValueError as exc:
        raise ValueError("transaction_date must be ISO YYYY-MM-DD") from exc
    gross = _decimal(row.gross_amount, "gross_amount")
    units = _decimal(row.units, "units")
    if gross is None and units is None:
        raise ValueError("each sales row requires gross_amount or units")
    currency = None
    if row.currency is not None:
        currency = _required(row.currency, "currency").upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a three-letter code")
    if gross is not None and currency is None:
        raise ValueError("gross_amount requires currency")
    return {
        "source_row_key": row_key,
        "transaction_date": transaction_date,
        "gross_amount_decimal": gross,
        "units_decimal": units,
        "currency": currency,
    }


def _sha(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def import_sales_batch(
    repository: RoyaltyRepository,
    org_id: str,
    agreement_id: str,
    source_system: str,
    source_dataset_id: str,
    rows: Iterable[NormalizedSalesRow],
    evidence_id: str,
    actor_id: str,
) -> ImportResult:
    repository.get_agreement(org_id, agreement_id)
    evidence = repository.get_evidence(org_id, evidence_id)
    source_system = _required(source_system, "source_system")
    source_dataset_id = _required(source_dataset_id, "source_dataset_id")
    materialized = tuple(rows)
    if not materialized:
        raise ValueError("sales import batch must contain at least one row")
    if len(materialized) > MAX_BATCH_ROWS:
        raise ValueError(f"sales import batch exceeds {MAX_BATCH_ROWS} rows")
    canonical = tuple(_canonical_row(row) for row in materialized)
    row_keys = [row["source_row_key"] for row in canonical]
    if len(row_keys) != len(set(row_keys)):
        raise ValueError("duplicate source_row_key within batch")
    dataset_payload = {
        "source_system": source_system,
        "source_dataset_id": source_dataset_id,
        "agreement_id": agreement_id,
        "evidence_sha256": evidence["source_sha256"],
        "rows": canonical,
    }
    dataset_sha = _sha(dataset_payload)

    try:
        repository.conn.execute("BEGIN")
        for row in canonical:
            row_sha = _sha({
                "source_system": source_system,
                "source_dataset_id": source_dataset_id,
                **row,
            })
            repository.conn.execute(
                """INSERT INTO sales_records(
                       id, agreement_id, source_dataset_id, source_row_key, transaction_date,
                       gross_amount_decimal, units_decimal, currency, row_sha256
                   ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    f"sale_{uuid.uuid4().hex}", agreement_id, source_dataset_id, row["source_row_key"],
                    row["transaction_date"], row["gross_amount_decimal"], row["units_decimal"], row["currency"], row_sha,
                ),
            )
        repository._audit(org_id, actor_id, "IMPORT", "SalesDataset", source_dataset_id, {
            "agreement_id": agreement_id,
            "source_system": source_system,
            "source_dataset_id": source_dataset_id,
            "dataset_sha256": dataset_sha,
            "evidence_id": evidence_id,
            "row_count": len(canonical),
        })
        repository.conn.commit()
    except sqlite3.IntegrityError as exc:
        repository.conn.rollback()
        raise ConflictError("sales dataset contains source rows already imported or violates integrity constraints") from exc
    except Exception:
        repository.conn.rollback()
        raise

    return ImportResult(
        source_dataset_id=source_dataset_id,
        source_system=source_system,
        row_count=len(canonical),
        dataset_sha256=dataset_sha,
        evidence_id=evidence_id,
    )


def list_sales_records(repository: RoyaltyRepository, org_id: str, agreement_id: str, source_dataset_id: Optional[str] = None) -> list[dict[str, Any]]:
    repository.get_agreement(org_id, agreement_id)
    sql = "SELECT * FROM sales_records WHERE agreement_id=?"
    params: list[Any] = [agreement_id]
    if source_dataset_id is not None:
        sql += " AND source_dataset_id=?"
        params.append(source_dataset_id)
    sql += " ORDER BY transaction_date, source_dataset_id, source_row_key"
    return [dict(row) for row in repository.conn.execute(sql, tuple(params)).fetchall()]
