from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from factory_cloud.billing_core import (
    BillingStateError,
    RevenueRecord,
    advance_revenue_record,
    money,
)


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS revenue_records (
    revenue_id TEXT PRIMARY KEY,
    factory_id TEXT NOT NULL,
    billing_owner_id TEXT NOT NULL,
    engagement_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    recovery_amount TEXT,
    platform_fee_amount TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN (
        'NOT_BILLABLE','FEE_EARNED','INVOICE_APPROVED','INVOICED',
        'PAYMENT_PENDING','PAID','RECONCILED'
    )),
    provider TEXT,
    provider_customer_ref TEXT,
    provider_invoice_ref TEXT,
    provider_payment_ref TEXT,
    evidence_ref TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(factory_id, engagement_id)
);
CREATE INDEX IF NOT EXISTS idx_revenue_records_factory_state
ON revenue_records(factory_id, state);
CREATE INDEX IF NOT EXISTS idx_revenue_records_provider_invoice
ON revenue_records(provider, provider_invoice_ref);

CREATE TABLE IF NOT EXISTS revenue_transitions (
    transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    revenue_id TEXT NOT NULL REFERENCES revenue_records(revenue_id) ON DELETE CASCADE,
    prior_state TEXT NOT NULL,
    new_state TEXT NOT NULL,
    evidence_ref TEXT,
    provider_event_id TEXT,
    occurred_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_revenue_transitions_record
ON revenue_transitions(revenue_id, transition_id);

CREATE TABLE IF NOT EXISTS billing_provider_events (
    provider TEXT NOT NULL,
    provider_event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    object_ref TEXT,
    payload_sha256 TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    PRIMARY KEY(provider, provider_event_id)
);
"""


PROVIDER_REF_FIELDS = {
    "customer": "provider_customer_ref",
    "invoice": "provider_invoice_ref",
    "payment": "provider_payment_ref",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_from_row(row: sqlite3.Row) -> RevenueRecord:
    return RevenueRecord(
        factory_id=row["factory_id"],
        engagement_id=row["engagement_id"],
        customer_id=row["customer_id"],
        currency=row["currency"],
        recovery_amount=Decimal(row["recovery_amount"]) if row["recovery_amount"] is not None else None,
        platform_fee_amount=Decimal(row["platform_fee_amount"]),
        state=row["state"],
        evidence_ref=row["evidence_ref"],
    )


class RevenueLedger:
    """Durable portfolio revenue truth, independent from customer recovery truth.

    Provider payloads are deliberately not persisted. Only minimal provider refs,
    event identity, event type and a payload hash are retained for audit/idempotency.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def create(self, record: RevenueRecord, *, billing_owner_id: str) -> str:
        revenue_id = str(uuid.uuid4())
        now = _now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    """
                    INSERT INTO revenue_records(
                        revenue_id,factory_id,billing_owner_id,engagement_id,customer_id,
                        currency,recovery_amount,platform_fee_amount,state,evidence_ref,
                        created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        revenue_id,
                        record.factory_id,
                        str(billing_owner_id),
                        record.engagement_id,
                        record.customer_id,
                        record.currency,
                        str(record.recovery_amount) if record.recovery_amount is not None else None,
                        str(record.platform_fee_amount),
                        record.state,
                        record.evidence_ref,
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                db.rollback()
                raise BillingStateError(
                    f"revenue record already exists for {record.factory_id}/{record.engagement_id}"
                ) from exc
            db.commit()
        return revenue_id

    def get(self, revenue_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM revenue_records WHERE revenue_id=?", (str(revenue_id),)
            ).fetchone()
        if row is None:
            raise KeyError(revenue_id)
        result = dict(row)
        result["recovery_amount"] = (
            Decimal(result["recovery_amount"]) if result["recovery_amount"] is not None else None
        )
        result["platform_fee_amount"] = Decimal(result["platform_fee_amount"])
        return result

    def find(self, factory_id: str, engagement_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                "SELECT revenue_id FROM revenue_records WHERE factory_id=? AND engagement_id=?",
                (str(factory_id), str(engagement_id)),
            ).fetchone()
        if row is None:
            raise KeyError((factory_id, engagement_id))
        return self.get(row["revenue_id"])

    def transition(
        self,
        revenue_id: str,
        new_state: str,
        *,
        evidence_ref: str | None = None,
        provider_event_id: str | None = None,
    ) -> dict[str, Any]:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM revenue_records WHERE revenue_id=?", (str(revenue_id),)
            ).fetchone()
            if row is None:
                db.rollback()
                raise KeyError(revenue_id)
            current = _record_from_row(row)
            updated = advance_revenue_record(current, new_state, evidence_ref=evidence_ref)
            now = _now()
            db.execute(
                """
                UPDATE revenue_records
                SET state=?, evidence_ref=?, updated_at=?
                WHERE revenue_id=?
                """,
                (updated.state, updated.evidence_ref, now, revenue_id),
            )
            db.execute(
                """
                INSERT INTO revenue_transitions(
                    revenue_id,prior_state,new_state,evidence_ref,provider_event_id,occurred_at
                ) VALUES(?,?,?,?,?,?)
                """,
                (
                    revenue_id,
                    current.state,
                    updated.state,
                    updated.evidence_ref,
                    str(provider_event_id) if provider_event_id else None,
                    now,
                ),
            )
            db.commit()
        return self.get(revenue_id)

    def attach_provider_ref(self, revenue_id: str, kind: str, value: str, *, provider: str) -> None:
        column = PROVIDER_REF_FIELDS.get(str(kind))
        if column is None:
            raise BillingStateError(f"unknown provider ref kind: {kind}")
        provider = str(provider).strip().lower()
        value = str(value).strip()
        if not provider or not value:
            raise BillingStateError("provider and provider ref are required")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                f"SELECT provider,{column} AS ref FROM revenue_records WHERE revenue_id=?",
                (str(revenue_id),),
            ).fetchone()
            if row is None:
                db.rollback()
                raise KeyError(revenue_id)
            if row["provider"] and row["provider"] != provider:
                db.rollback()
                raise BillingStateError("provider ownership cannot be silently changed")
            if row["ref"] and row["ref"] != value:
                db.rollback()
                raise BillingStateError(f"{kind} provider ref cannot be silently replaced")
            db.execute(
                f"UPDATE revenue_records SET provider=?, {column}=?, updated_at=? WHERE revenue_id=?",
                (provider, value, _now(), revenue_id),
            )
            db.commit()

    def record_provider_event(
        self,
        *,
        provider: str,
        provider_event_id: str,
        event_type: str,
        object_ref: str | None,
        payload: bytes | str,
    ) -> bool:
        provider = str(provider).strip().lower()
        provider_event_id = str(provider_event_id).strip()
        event_type = str(event_type).strip()
        if not provider or not provider_event_id or not event_type:
            raise BillingStateError("provider event identity is incomplete")
        raw = payload if isinstance(payload, bytes) else str(payload).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                """
                SELECT payload_sha256,event_type,object_ref
                FROM billing_provider_events
                WHERE provider=? AND provider_event_id=?
                """,
                (provider, provider_event_id),
            ).fetchone()
            if existing is not None:
                if (
                    existing["payload_sha256"] != digest
                    or existing["event_type"] != event_type
                    or (existing["object_ref"] or None) != (str(object_ref) if object_ref else None)
                ):
                    db.rollback()
                    raise BillingStateError("provider event id was reused with conflicting evidence")
                db.rollback()
                return False
            db.execute(
                """
                INSERT INTO billing_provider_events(
                    provider,provider_event_id,event_type,object_ref,payload_sha256,observed_at
                ) VALUES(?,?,?,?,?,?)
                """,
                (
                    provider,
                    provider_event_id,
                    event_type,
                    str(object_ref) if object_ref else None,
                    digest,
                    _now(),
                ),
            )
            db.commit()
        return True

    def transitions(self, revenue_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT prior_state,new_state,evidence_ref,provider_event_id,occurred_at
                FROM revenue_transitions
                WHERE revenue_id=? ORDER BY transition_id
                """,
                (str(revenue_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def report(self) -> dict[str, Any]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT factory_id,state,platform_fee_amount,recovery_amount FROM revenue_records"
            ).fetchall()
        by_factory: dict[str, dict[str, Any]] = {}
        total_platform = Decimal("0.00")
        total_recovery = Decimal("0.00")
        for row in rows:
            factory = by_factory.setdefault(
                row["factory_id"],
                {"platform_fee_amount": Decimal("0.00"), "recovery_amount": Decimal("0.00"), "states": {}},
            )
            fee = money(row["platform_fee_amount"])
            recovery = money(row["recovery_amount"]) if row["recovery_amount"] is not None else Decimal("0.00")
            factory["platform_fee_amount"] += fee
            factory["recovery_amount"] += recovery
            factory["states"][row["state"]] = factory["states"].get(row["state"], 0) + 1
            total_platform += fee
            total_recovery += recovery
        return {
            "platform_revenue_amount": total_platform,
            "customer_recovery_amount": total_recovery,
            "by_factory": by_factory,
        }

    def export_record(self, revenue_id: str) -> dict[str, Any]:
        record = self.get(revenue_id)
        return {
            **record,
            "recovery_amount": str(record["recovery_amount"]) if record["recovery_amount"] is not None else None,
            "platform_fee_amount": str(record["platform_fee_amount"]),
            "transitions": self.transitions(revenue_id),
        }
