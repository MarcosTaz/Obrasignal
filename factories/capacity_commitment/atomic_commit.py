from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from decimal import Decimal

from .engine import ENGINE_VERSION, evaluate_recoverability
from .state import AssistedCaseState, dump_state, load_state
from .workflow import WorkflowEvent, WorkflowEventType, validate_event


def _event_row_matches(row: sqlite3.Row, event: WorkflowEvent) -> bool:
    amount_text = None if event.amount is None else format(event.amount, "f")
    return (
        row["tenant_id"] == event.tenant_id
        and row["event_id"] == event.event_id
        and row["engagement_id"] == event.engagement_id
        and row["event_type"] == event.event_type.value
        and row["occurred_at"] == event.occurred_at
        and row["case_id"] == event.case_id
        and row["amount"] == amount_text
        and row["currency"] == event.currency
        and row["external_ref"] == event.external_ref
        and row["note"] == event.note
    )


def commit_case_and_link(
    *,
    db_path: str,
    state: AssistedCaseState,
    engagement_id: str,
    link_event: WorkflowEvent,
) -> tuple[bool, bool]:
    """Persist a reviewed case and CASE_LINKED event in one transaction.

    Exact retries are idempotent. Any changed duplicate or identity mismatch aborts
    the transaction. A pre-existing identical case without its link can be repaired
    by adding the missing link; an orphan link without a case is treated as corrupt.
    """

    if not db_path:
        raise ValueError("db_path is required")
    if link_event.event_type is not WorkflowEventType.CASE_LINKED:
        raise ValueError("link_event must be CASE_LINKED")
    link_event = validate_event(link_event)
    if link_event.tenant_id != state.tenant_id:
        raise PermissionError("link event tenant does not match case tenant")
    if link_event.engagement_id != engagement_id:
        raise ValueError("link event engagement_id mismatch")
    if link_event.case_id != state.recovery_case.case_id:
        raise ValueError("link event case_id mismatch")

    evaluate_recoverability(state.recovery_case)
    snapshot = dump_state(state)
    now = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN IMMEDIATE")
        engagement = conn.execute(
            """
            SELECT tenant_id, engagement_id, company_id, customer_id, program_id, currency
            FROM capacity_commitment_engagements
            WHERE tenant_id=? AND engagement_id=?
            """,
            (state.tenant_id, engagement_id),
        ).fetchone()
        if engagement is None:
            raise KeyError("engagement not found")
        mismatches = []
        if state.company_id != engagement["company_id"]:
            mismatches.append("company_id")
        if state.customer_id != engagement["customer_id"]:
            mismatches.append("customer_id")
        if state.program_id != engagement["program_id"]:
            mismatches.append("program_id")
        if state.recovery_case.currency.upper() != engagement["currency"]:
            mismatches.append("currency")
        if mismatches:
            raise ValueError("case does not match engagement: " + ", ".join(mismatches))

        case_id = state.recovery_case.case_id
        case_row = conn.execute(
            """
            SELECT snapshot, engine_version FROM capacity_commitment_cases
            WHERE tenant_id=? AND case_id=?
            """,
            (state.tenant_id, case_id),
        ).fetchone()
        event_row = conn.execute(
            """
            SELECT tenant_id, event_id, engagement_id, event_type, occurred_at, case_id,
                   amount, currency, external_ref, note
            FROM capacity_commitment_workflow_events
            WHERE tenant_id=? AND event_id=?
            """,
            (state.tenant_id, link_event.event_id),
        ).fetchone()

        if case_row is None and event_row is not None:
            raise RuntimeError("orphan CASE_LINKED event exists without case")

        case_created = False
        if case_row is None:
            conn.execute(
                """
                INSERT INTO capacity_commitment_cases
                    (tenant_id, case_id, snapshot, engine_version, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (state.tenant_id, case_id, snapshot, ENGINE_VERSION, now),
            )
            case_created = True
        else:
            if case_row["engine_version"] != ENGINE_VERSION:
                raise RuntimeError("case requires explicit reassessment for engine version drift")
            if case_row["snapshot"] != snapshot:
                raise FileExistsError("case already exists with different source state")
            # Re-parse stored data before accepting an idempotent retry.
            stored = load_state(case_row["snapshot"], expected_tenant_id=state.tenant_id)
            evaluate_recoverability(stored.recovery_case)

        link_created = False
        if event_row is None:
            amount_text = None if link_event.amount is None else format(link_event.amount, "f")
            conn.execute(
                """
                INSERT INTO capacity_commitment_workflow_events
                (tenant_id, event_id, engagement_id, event_type, occurred_at, case_id,
                 amount, currency, external_ref, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link_event.tenant_id,
                    link_event.event_id,
                    link_event.engagement_id,
                    link_event.event_type.value,
                    link_event.occurred_at,
                    link_event.case_id,
                    amount_text,
                    link_event.currency,
                    link_event.external_ref,
                    link_event.note,
                    now,
                ),
            )
            link_created = True
        elif not _event_row_matches(event_row, link_event):
            raise FileExistsError("CASE_LINKED event already exists with different content")

        conn.commit()
        return case_created, link_created
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
