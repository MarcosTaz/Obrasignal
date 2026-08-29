from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path

from .workflow import WorkflowRepository


_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")


class SupportCategory(str, Enum):
    DATA = "DATA"
    CONTRACT = "CONTRACT"
    CALCULATION = "CALCULATION"
    ACCESS = "ACCESS"
    BILLING = "BILLING"
    OTHER = "OTHER"


class SupportEventType(str, Enum):
    ACKNOWLEDGED = "ACKNOWLEDGED"
    NOTE = "NOTE"
    RESOLVED = "RESOLVED"
    REOPENED = "REOPENED"


@dataclass(frozen=True)
class MonitoringPlan:
    tenant_id: str
    monitor_id: str
    engagement_id: str
    case_id: str
    cadence_days: int
    next_check_on: str
    supersedes_monitor_id: str | None = None


@dataclass(frozen=True)
class SupportTicket:
    tenant_id: str
    ticket_id: str
    engagement_id: str
    category: SupportCategory
    summary: str
    opened_at: str
    case_id: str | None = None


@dataclass(frozen=True)
class SupportEvent:
    tenant_id: str
    support_event_id: str
    ticket_id: str
    event_type: SupportEventType
    occurred_at: str
    note: str | None = None


@dataclass(frozen=True)
class SupportState:
    ticket_id: str
    status: str
    event_count: int
    latest_event_type: str | None


def _text(value, field, *, max_len=500):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    value = value.strip()
    if len(value) > max_len or "\x00" in value:
        raise ValueError(f"{field} is invalid")
    return value


def _safe_id(value, field):
    value = _text(value, field, max_len=200)
    if not _SAFE_ID_RE.fullmatch(value):
        raise ValueError(f"{field} contains unsupported characters")
    return value


def _optional_text(value, field, *, max_len=500):
    if value is None:
        return None
    return _text(value, field, max_len=max_len)


def validate_monitor(plan: MonitoringPlan) -> MonitoringPlan:
    if type(plan.cadence_days) is not int or plan.cadence_days < 1 or plan.cadence_days > 365:
        raise ValueError("cadence_days must be an integer from 1 to 365")
    try:
        date.fromisoformat(plan.next_check_on)
    except (TypeError, ValueError) as exc:
        raise ValueError("next_check_on must be YYYY-MM-DD") from exc
    return MonitoringPlan(
        tenant_id=_text(plan.tenant_id, "tenant_id", max_len=200),
        monitor_id=_safe_id(plan.monitor_id, "monitor_id"),
        engagement_id=_safe_id(plan.engagement_id, "engagement_id"),
        case_id=_safe_id(plan.case_id, "case_id"),
        cadence_days=plan.cadence_days,
        next_check_on=plan.next_check_on,
        supersedes_monitor_id=None
        if plan.supersedes_monitor_id is None
        else _safe_id(plan.supersedes_monitor_id, "supersedes_monitor_id"),
    )


def validate_ticket(ticket: SupportTicket) -> SupportTicket:
    if not isinstance(ticket.category, SupportCategory):
        raise ValueError("category must be a SupportCategory")
    return SupportTicket(
        tenant_id=_text(ticket.tenant_id, "tenant_id", max_len=200),
        ticket_id=_safe_id(ticket.ticket_id, "ticket_id"),
        engagement_id=_safe_id(ticket.engagement_id, "engagement_id"),
        category=ticket.category,
        summary=_text(ticket.summary, "summary", max_len=1000),
        opened_at=_text(ticket.opened_at, "opened_at", max_len=80),
        case_id=None if ticket.case_id is None else _safe_id(ticket.case_id, "case_id"),
    )


def validate_support_event(event: SupportEvent) -> SupportEvent:
    if not isinstance(event.event_type, SupportEventType):
        raise ValueError("event_type must be a SupportEventType")
    return SupportEvent(
        tenant_id=_text(event.tenant_id, "tenant_id", max_len=200),
        support_event_id=_safe_id(event.support_event_id, "support_event_id"),
        ticket_id=_safe_id(event.ticket_id, "ticket_id"),
        event_type=event.event_type,
        occurred_at=_text(event.occurred_at, "occurred_at", max_len=80),
        note=_optional_text(event.note, "note", max_len=2000),
    )


class ServiceOperationsRepository:
    """Tenant-scoped monitoring plans and append-only support/incident trail."""

    def __init__(self, db_path: str):
        if not db_path or db_path == ":memory:":
            raise ValueError("db_path must be durable")
        self.db_path = str(Path(db_path))
        self.workflow = WorkflowRepository(self.db_path)
        self._ensure_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS capacity_commitment_monitoring_plans (
                    tenant_id TEXT NOT NULL,
                    monitor_id TEXT NOT NULL,
                    engagement_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    cadence_days TEXT NOT NULL,
                    next_check_on TEXT NOT NULL,
                    supersedes_monitor_id TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, monitor_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS capacity_commitment_support_tickets (
                    tenant_id TEXT NOT NULL,
                    ticket_id TEXT NOT NULL,
                    engagement_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    opened_at TEXT NOT NULL,
                    case_id TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, ticket_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS capacity_commitment_support_events (
                    tenant_id TEXT NOT NULL,
                    support_event_id TEXT NOT NULL,
                    ticket_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    note TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, support_event_id)
                )
                """
            )

    def _validate_engagement_case(self, *, tenant_id, engagement_id, case_id=None):
        engagement = self.workflow.load_engagement(
            tenant_id=tenant_id, engagement_id=engagement_id
        )
        if case_id is not None:
            with self._connect() as conn:
                self.workflow._validate_case_binding(conn, engagement, case_id)
        return engagement

    def save_monitor(self, plan: MonitoringPlan) -> bool:
        plan = validate_monitor(plan)
        self._validate_engagement_case(
            tenant_id=plan.tenant_id,
            engagement_id=plan.engagement_id,
            case_id=plan.case_id,
        )
        if plan.supersedes_monitor_id is not None:
            previous = self.load_monitor(
                tenant_id=plan.tenant_id, monitor_id=plan.supersedes_monitor_id
            )
            if previous.engagement_id != plan.engagement_id or previous.case_id != plan.case_id:
                raise ValueError("superseded monitor must target the same engagement and case")
        now = datetime.now(timezone.utc).isoformat()
        values = (
            plan.tenant_id,
            plan.monitor_id,
            plan.engagement_id,
            plan.case_id,
            str(plan.cadence_days),
            plan.next_check_on,
            plan.supersedes_monitor_id,
            now,
        )
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO capacity_commitment_monitoring_plans
                    (tenant_id, monitor_id, engagement_id, case_id, cadence_days,
                     next_check_on, supersedes_monitor_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
            return True
        except sqlite3.IntegrityError as exc:
            if self.load_monitor(tenant_id=plan.tenant_id, monitor_id=plan.monitor_id) == plan:
                return False
            raise FileExistsError("monitoring plan already exists with different content") from exc

    def load_monitor(self, *, tenant_id: str, monitor_id: str) -> MonitoringPlan:
        tenant_id = _text(tenant_id, "tenant_id", max_len=200)
        monitor_id = _safe_id(monitor_id, "monitor_id")
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT tenant_id, monitor_id, engagement_id, case_id, cadence_days,
                       next_check_on, supersedes_monitor_id
                FROM capacity_commitment_monitoring_plans
                WHERE tenant_id=? AND monitor_id=?
                """,
                (tenant_id, monitor_id),
            ).fetchone()
        if row is None:
            raise KeyError("monitoring plan not found")
        return validate_monitor(
            MonitoringPlan(
                tenant_id=row["tenant_id"],
                monitor_id=row["monitor_id"],
                engagement_id=row["engagement_id"],
                case_id=row["case_id"],
                cadence_days=int(row["cadence_days"]),
                next_check_on=row["next_check_on"],
                supersedes_monitor_id=row["supersedes_monitor_id"],
            )
        )

    def list_active_monitors(self, *, tenant_id: str) -> list[MonitoringPlan]:
        tenant_id = _text(tenant_id, "tenant_id", max_len=200)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT monitor_id FROM capacity_commitment_monitoring_plans m
                WHERE tenant_id=? AND NOT EXISTS (
                    SELECT 1 FROM capacity_commitment_monitoring_plans newer
                    WHERE newer.tenant_id=m.tenant_id AND newer.supersedes_monitor_id=m.monitor_id
                )
                ORDER BY monitor_id
                """,
                (tenant_id,),
            ).fetchall()
        return [self.load_monitor(tenant_id=tenant_id, monitor_id=row["monitor_id"]) for row in rows]

    def open_ticket(self, ticket: SupportTicket) -> bool:
        ticket = validate_ticket(ticket)
        self._validate_engagement_case(
            tenant_id=ticket.tenant_id,
            engagement_id=ticket.engagement_id,
            case_id=ticket.case_id,
        )
        now = datetime.now(timezone.utc).isoformat()
        values = (
            ticket.tenant_id,
            ticket.ticket_id,
            ticket.engagement_id,
            ticket.category.value,
            ticket.summary,
            ticket.opened_at,
            ticket.case_id,
            now,
        )
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO capacity_commitment_support_tickets
                    (tenant_id, ticket_id, engagement_id, category, summary,
                     opened_at, case_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
            return True
        except sqlite3.IntegrityError as exc:
            if self.load_ticket(tenant_id=ticket.tenant_id, ticket_id=ticket.ticket_id) == ticket:
                return False
            raise FileExistsError("support ticket already exists with different content") from exc

    def load_ticket(self, *, tenant_id: str, ticket_id: str) -> SupportTicket:
        tenant_id = _text(tenant_id, "tenant_id", max_len=200)
        ticket_id = _safe_id(ticket_id, "ticket_id")
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT tenant_id, ticket_id, engagement_id, category, summary, opened_at, case_id
                FROM capacity_commitment_support_tickets WHERE tenant_id=? AND ticket_id=?
                """,
                (tenant_id, ticket_id),
            ).fetchone()
        if row is None:
            raise KeyError("support ticket not found")
        return validate_ticket(
            SupportTicket(
                tenant_id=row["tenant_id"],
                ticket_id=row["ticket_id"],
                engagement_id=row["engagement_id"],
                category=SupportCategory(row["category"]),
                summary=row["summary"],
                opened_at=row["opened_at"],
                case_id=row["case_id"],
            )
        )

    def append_support_event(self, event: SupportEvent) -> bool:
        event = validate_support_event(event)
        self.load_ticket(tenant_id=event.tenant_id, ticket_id=event.ticket_id)
        now = datetime.now(timezone.utc).isoformat()
        values = (
            event.tenant_id,
            event.support_event_id,
            event.ticket_id,
            event.event_type.value,
            event.occurred_at,
            event.note,
            now,
        )
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO capacity_commitment_support_events
                    (tenant_id, support_event_id, ticket_id, event_type, occurred_at, note, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
            return True
        except sqlite3.IntegrityError as exc:
            if self.load_support_event(
                tenant_id=event.tenant_id, support_event_id=event.support_event_id
            ) == event:
                return False
            raise FileExistsError("support event already exists with different content") from exc

    def load_support_event(self, *, tenant_id: str, support_event_id: str) -> SupportEvent:
        tenant_id = _text(tenant_id, "tenant_id", max_len=200)
        support_event_id = _safe_id(support_event_id, "support_event_id")
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT tenant_id, support_event_id, ticket_id, event_type, occurred_at, note
                FROM capacity_commitment_support_events
                WHERE tenant_id=? AND support_event_id=?
                """,
                (tenant_id, support_event_id),
            ).fetchone()
        if row is None:
            raise KeyError("support event not found")
        return validate_support_event(
            SupportEvent(
                tenant_id=row["tenant_id"],
                support_event_id=row["support_event_id"],
                ticket_id=row["ticket_id"],
                event_type=SupportEventType(row["event_type"]),
                occurred_at=row["occurred_at"],
                note=row["note"],
            )
        )

    def support_state(self, *, tenant_id: str, ticket_id: str) -> SupportState:
        self.load_ticket(tenant_id=tenant_id, ticket_id=ticket_id)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT support_event_id FROM capacity_commitment_support_events
                WHERE tenant_id=? AND ticket_id=? ORDER BY created_at, support_event_id
                """,
                (tenant_id, ticket_id),
            ).fetchall()
        events = [
            self.load_support_event(tenant_id=tenant_id, support_event_id=row["support_event_id"])
            for row in rows
        ]
        status = "OPEN"
        for event in events:
            if event.event_type is SupportEventType.RESOLVED:
                status = "RESOLVED"
            elif event.event_type is SupportEventType.REOPENED:
                status = "OPEN"
        return SupportState(
            ticket_id=ticket_id,
            status=status,
            event_count=len(events),
            latest_event_type=events[-1].event_type.value if events else None,
        )
