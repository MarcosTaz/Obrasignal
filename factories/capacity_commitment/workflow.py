from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Context, Decimal, InvalidOperation, localcontext
from enum import Enum
from pathlib import Path

from .state import load_state


_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
_MONEY_CONTEXT = Context(prec=60, Emin=-999999, Emax=999999)


class WorkflowEventType(str, Enum):
    CASE_LINKED = "CASE_LINKED"
    ACTION_PREPARED = "ACTION_PREPARED"
    ACTION_SUBMITTED = "ACTION_SUBMITTED"
    CUSTOMER_ACKNOWLEDGED = "CUSTOMER_ACKNOWLEDGED"
    CUSTOMER_DISPUTED = "CUSTOMER_DISPUTED"
    CUSTOMER_ACCEPTED = "CUSTOMER_ACCEPTED"
    CUSTOMER_REJECTED = "CUSTOMER_REJECTED"
    CUSTOMER_RECOVERY_RECEIVED = "CUSTOMER_RECOVERY_RECEIVED"
    OUTCOME_ZERO_CONFIRMED = "OUTCOME_ZERO_CONFIRMED"
    OUTCOME_CLOSED = "OUTCOME_CLOSED"
    OUR_INVOICE_ISSUED = "OUR_INVOICE_ISSUED"
    OUR_PAYMENT_RECEIVED = "OUR_PAYMENT_RECEIVED"
    MONITORING_CHECK = "MONITORING_CHECK"
    MONITORING_ALERT = "MONITORING_ALERT"


_MONEY_EVENTS = {
    WorkflowEventType.CUSTOMER_RECOVERY_RECEIVED,
    WorkflowEventType.OUR_INVOICE_ISSUED,
    WorkflowEventType.OUR_PAYMENT_RECEIVED,
}
_CASE_REQUIRED_EVENTS = {
    WorkflowEventType.CASE_LINKED,
    WorkflowEventType.ACTION_PREPARED,
    WorkflowEventType.ACTION_SUBMITTED,
    WorkflowEventType.CUSTOMER_ACKNOWLEDGED,
    WorkflowEventType.CUSTOMER_DISPUTED,
    WorkflowEventType.CUSTOMER_ACCEPTED,
    WorkflowEventType.CUSTOMER_REJECTED,
    WorkflowEventType.CUSTOMER_RECOVERY_RECEIVED,
    WorkflowEventType.OUTCOME_ZERO_CONFIRMED,
    WorkflowEventType.OUTCOME_CLOSED,
    WorkflowEventType.MONITORING_CHECK,
    WorkflowEventType.MONITORING_ALERT,
}


@dataclass(frozen=True)
class Engagement:
    tenant_id: str
    engagement_id: str
    company_id: str
    customer_id: str
    program_id: str
    currency: str


@dataclass(frozen=True)
class WorkflowEvent:
    tenant_id: str
    event_id: str
    engagement_id: str
    event_type: WorkflowEventType
    occurred_at: str
    case_id: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    external_ref: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class EngagementSummary:
    engagement_id: str
    linked_case_ids: tuple[str, ...]
    customer_recovery_received: Decimal
    our_invoice_issued: Decimal
    our_payment_received: Decimal
    action_submitted: bool
    customer_accepted: bool
    customer_rejected: bool
    zero_outcome_confirmed: bool
    latest_event_type: str | None


def _text(value, field: str, *, max_len=500) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    value = value.strip()
    if len(value) > max_len or "\x00" in value:
        raise ValueError(f"{field} is invalid")
    return value


def _safe_id(value, field: str) -> str:
    value = _text(value, field, max_len=200)
    if not _SAFE_ID_RE.fullmatch(value):
        raise ValueError(f"{field} contains unsupported characters")
    return value


def _currency(value, *, allow_none=False):
    if value is None and allow_none:
        return None
    value = _text(value, "currency", max_len=3).upper()
    if len(value) != 3 or not value.isascii() or not value.isalpha():
        raise ValueError("currency must be a 3-letter ASCII code")
    return value


def _money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError("amount must be a finite non-negative Decimal")
    return value


def _optional_text(value, field, *, max_len=500):
    if value is None:
        return None
    return _text(value, field, max_len=max_len)


def validate_engagement(engagement: Engagement) -> Engagement:
    return Engagement(
        tenant_id=_text(engagement.tenant_id, "tenant_id", max_len=200),
        engagement_id=_safe_id(engagement.engagement_id, "engagement_id"),
        company_id=_text(engagement.company_id, "company_id", max_len=200),
        customer_id=_text(engagement.customer_id, "customer_id", max_len=200),
        program_id=_text(engagement.program_id, "program_id", max_len=200),
        currency=_currency(engagement.currency),
    )


def validate_event(event: WorkflowEvent) -> WorkflowEvent:
    if not isinstance(event.event_type, WorkflowEventType):
        raise ValueError("event_type must be a WorkflowEventType")
    event_id = _safe_id(event.event_id, "event_id")
    engagement_id = _safe_id(event.engagement_id, "engagement_id")
    case_id = None if event.case_id is None else _safe_id(event.case_id, "case_id")
    amount = _money(event.amount)
    currency = _currency(event.currency, allow_none=True)
    if event.event_type in _MONEY_EVENTS:
        if amount is None or currency is None:
            raise ValueError("monetary workflow event requires amount and currency")
    elif amount is not None or currency is not None:
        raise ValueError("non-monetary workflow event must not carry amount/currency")
    if event.event_type in _CASE_REQUIRED_EVENTS and case_id is None:
        raise ValueError(f"{event.event_type.value} requires case_id")
    return WorkflowEvent(
        tenant_id=_text(event.tenant_id, "tenant_id", max_len=200),
        event_id=event_id,
        engagement_id=engagement_id,
        event_type=event.event_type,
        occurred_at=_text(event.occurred_at, "occurred_at", max_len=80),
        case_id=case_id,
        amount=amount,
        currency=currency,
        external_ref=_optional_text(event.external_ref, "external_ref", max_len=300),
        note=_optional_text(event.note, "note", max_len=2000),
    )


class WorkflowRepository:
    """Append-only operational ledger for engagement → action → outcome → payment."""

    def __init__(self, db_path: str):
        if not db_path or db_path == ":memory:":
            raise ValueError("db_path must be durable")
        self.db_path = str(Path(db_path))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS capacity_commitment_engagements (
                    tenant_id TEXT NOT NULL,
                    engagement_id TEXT NOT NULL,
                    company_id TEXT NOT NULL,
                    customer_id TEXT NOT NULL,
                    program_id TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, engagement_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS capacity_commitment_workflow_events (
                    tenant_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    engagement_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    case_id TEXT,
                    amount TEXT,
                    currency TEXT,
                    external_ref TEXT,
                    note TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, event_id)
                )
                """
            )

    def save_engagement(self, engagement: Engagement) -> bool:
        engagement = validate_engagement(engagement)
        now = datetime.now(timezone.utc).isoformat()
        values = (
            engagement.tenant_id,
            engagement.engagement_id,
            engagement.company_id,
            engagement.customer_id,
            engagement.program_id,
            engagement.currency,
            now,
        )
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO capacity_commitment_engagements
                    (tenant_id, engagement_id, company_id, customer_id, program_id, currency, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
            return True
        except sqlite3.IntegrityError as exc:
            if self.load_engagement(
                tenant_id=engagement.tenant_id,
                engagement_id=engagement.engagement_id,
            ) == engagement:
                return False
            raise FileExistsError("engagement identity already exists with different scope") from exc

    def load_engagement(self, *, tenant_id: str, engagement_id: str) -> Engagement:
        tenant_id = _text(tenant_id, "tenant_id", max_len=200)
        engagement_id = _safe_id(engagement_id, "engagement_id")
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT tenant_id, engagement_id, company_id, customer_id, program_id, currency
                FROM capacity_commitment_engagements WHERE tenant_id=? AND engagement_id=?
                """,
                (tenant_id, engagement_id),
            ).fetchone()
        if row is None:
            raise KeyError("engagement not found")
        return validate_engagement(Engagement(**dict(row)))

    def list_engagements(self, *, tenant_id: str) -> list[Engagement]:
        tenant_id = _text(tenant_id, "tenant_id", max_len=200)
        with self._connect() as conn:
            ids = [row["engagement_id"] for row in conn.execute(
                "SELECT engagement_id FROM capacity_commitment_engagements WHERE tenant_id=? ORDER BY engagement_id",
                (tenant_id,),
            ).fetchall()]
        return [self.load_engagement(tenant_id=tenant_id, engagement_id=item) for item in ids]

    def _validate_case_binding(self, conn, engagement: Engagement, case_id: str) -> None:
        row = conn.execute(
            "SELECT snapshot FROM capacity_commitment_cases WHERE tenant_id=? AND case_id=?",
            (engagement.tenant_id, case_id),
        ).fetchone()
        if row is None:
            raise KeyError("case not found")
        state = load_state(row["snapshot"], expected_tenant_id=engagement.tenant_id)
        mismatches = []
        if state.company_id != engagement.company_id:
            mismatches.append("company_id")
        if state.customer_id != engagement.customer_id:
            mismatches.append("customer_id")
        if state.program_id != engagement.program_id:
            mismatches.append("program_id")
        if state.recovery_case.currency.upper() != engagement.currency:
            mismatches.append("currency")
        if mismatches:
            raise ValueError("case does not match engagement: " + ", ".join(mismatches))

    def append_event(self, event: WorkflowEvent) -> bool:
        event = validate_event(event)
        engagement = self.load_engagement(
            tenant_id=event.tenant_id, engagement_id=event.engagement_id
        )
        if event.currency is not None and event.currency != engagement.currency:
            raise ValueError("event currency does not match engagement currency")
        amount_text = None if event.amount is None else format(event.amount, "f")
        now = datetime.now(timezone.utc).isoformat()
        values = (
            event.tenant_id,
            event.event_id,
            event.engagement_id,
            event.event_type.value,
            event.occurred_at,
            event.case_id,
            amount_text,
            event.currency,
            event.external_ref,
            event.note,
            now,
        )
        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                if event.case_id is not None:
                    self._validate_case_binding(conn, engagement, event.case_id)
                conn.execute(
                    """
                    INSERT INTO capacity_commitment_workflow_events
                    (tenant_id, event_id, engagement_id, event_type, occurred_at, case_id,
                     amount, currency, external_ref, note, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
            return True
        except sqlite3.IntegrityError as exc:
            if self.load_event(tenant_id=event.tenant_id, event_id=event.event_id) == event:
                return False
            raise FileExistsError("workflow event already exists with different content") from exc

    def load_event(self, *, tenant_id: str, event_id: str) -> WorkflowEvent:
        tenant_id = _text(tenant_id, "tenant_id", max_len=200)
        event_id = _safe_id(event_id, "event_id")
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT tenant_id, event_id, engagement_id, event_type, occurred_at, case_id,
                       amount, currency, external_ref, note
                FROM capacity_commitment_workflow_events WHERE tenant_id=? AND event_id=?
                """,
                (tenant_id, event_id),
            ).fetchone()
        if row is None:
            raise KeyError("workflow event not found")
        amount = None
        if row["amount"] is not None:
            try:
                amount = Decimal(row["amount"])
            except InvalidOperation as exc:
                raise RuntimeError("stored workflow amount is invalid") from exc
        return validate_event(
            WorkflowEvent(
                tenant_id=row["tenant_id"],
                event_id=row["event_id"],
                engagement_id=row["engagement_id"],
                event_type=WorkflowEventType(row["event_type"]),
                occurred_at=row["occurred_at"],
                case_id=row["case_id"],
                amount=amount,
                currency=row["currency"],
                external_ref=row["external_ref"],
                note=row["note"],
            )
        )

    def list_events(self, *, tenant_id: str, engagement_id: str) -> list[WorkflowEvent]:
        engagement = self.load_engagement(tenant_id=tenant_id, engagement_id=engagement_id)
        with self._connect() as conn:
            ids = [row["event_id"] for row in conn.execute(
                """
                SELECT event_id FROM capacity_commitment_workflow_events
                WHERE tenant_id=? AND engagement_id=? ORDER BY created_at, event_id
                """,
                (engagement.tenant_id, engagement.engagement_id),
            ).fetchall()]
        return [self.load_event(tenant_id=tenant_id, event_id=item) for item in ids]

    def summary(self, *, tenant_id: str, engagement_id: str) -> EngagementSummary:
        events = self.list_events(tenant_id=tenant_id, engagement_id=engagement_id)
        with localcontext(_MONEY_CONTEXT):
            recovery = sum(
                (event.amount for event in events if event.event_type is WorkflowEventType.CUSTOMER_RECOVERY_RECEIVED and event.amount is not None),
                Decimal("0"),
            )
            invoiced = sum(
                (event.amount for event in events if event.event_type is WorkflowEventType.OUR_INVOICE_ISSUED and event.amount is not None),
                Decimal("0"),
            )
            paid = sum(
                (event.amount for event in events if event.event_type is WorkflowEventType.OUR_PAYMENT_RECEIVED and event.amount is not None),
                Decimal("0"),
            )
        return EngagementSummary(
            engagement_id=engagement_id,
            linked_case_ids=tuple(sorted({event.case_id for event in events if event.case_id})),
            customer_recovery_received=recovery,
            our_invoice_issued=invoiced,
            our_payment_received=paid,
            action_submitted=any(event.event_type is WorkflowEventType.ACTION_SUBMITTED for event in events),
            customer_accepted=any(event.event_type is WorkflowEventType.CUSTOMER_ACCEPTED for event in events),
            customer_rejected=any(event.event_type is WorkflowEventType.CUSTOMER_REJECTED for event in events),
            zero_outcome_confirmed=any(event.event_type is WorkflowEventType.OUTCOME_ZERO_CONFIRMED for event in events),
            latest_event_type=events[-1].event_type.value if events else None,
        )
