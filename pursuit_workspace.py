"""Tenant-private pursuit workspace orchestration for an Opportunity.

The workspace owns pursuit context only. Canonical Opportunity data and optional
capability data remain owned by their respective modules. Optional summaries are
consumed through registered public providers and fail independently.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping, Protocol

WORKSPACE_STATUSES = {"ACTIVE", "ON_HOLD", "CLOSED", "ARCHIVED"}
REVIEW_STATES = {"NOT_REVIEWED", "IN_REVIEW", "REVIEWED", "NEEDS_ATTENTION"}
SUBMISSION_STATES = {"NOT_STARTED", "PREPARING", "READY_FOR_FINAL_REVIEW", "READY_TO_SUBMIT", "SUBMITTED", "UNKNOWN"}
MAX_TITLE = 300
MAX_NOTE = 8000
MAX_QUESTION = 2000

OPTIONAL_SECTIONS = (
    "decision", "milestones", "requirements", "readiness", "documents",
    "changes", "economics", "evidence",
)


class SummaryProvider(Protocol):
    """Small public contract implemented by optional capability adapters."""
    def summary(self, *, account_id: str, opportunity_id: int) -> Mapping: ...


@dataclass(frozen=True)
class ProviderRegistry:
    providers: Mapping[str, SummaryProvider]

    def get(self, name: str) -> SummaryProvider | None:
        return self.providers.get(name)


EMPTY_PROVIDERS = ProviderRegistry({})


def _now(clock: Callable[[], datetime] | None = None) -> str:
    value = (clock or (lambda: datetime.now(timezone.utc)))()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def ensure_workspace_tables(conn) -> None:
    # SQLite foreign-key enforcement is connection-scoped and defaults OFF.
    # Enable it before any workspace schema/write so declared FKs are real runtime guards.
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("""CREATE TABLE IF NOT EXISTS pursuit_workspaces(
        workspace_id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id TEXT NOT NULL,
        opportunity_id INTEGER NOT NULL,
        owner_id TEXT,
        workspace_status TEXT NOT NULL DEFAULT 'ACTIVE',
        review_state TEXT NOT NULL DEFAULT 'NOT_REVIEWED',
        submission_state TEXT NOT NULL DEFAULT 'NOT_STARTED',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(account_id, opportunity_id),
        FOREIGN KEY(opportunity_id) REFERENCES tenders(id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS pursuit_workspace_blockers(
        blocker_id INTEGER PRIMARY KEY AUTOINCREMENT,
        workspace_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'OPEN',
        severity TEXT,
        created_by TEXT,
        created_at TEXT NOT NULL,
        resolved_at TEXT,
        FOREIGN KEY(workspace_id) REFERENCES pursuit_workspaces(workspace_id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS pursuit_workspace_notes(
        note_id INTEGER PRIMARY KEY AUTOINCREMENT,
        workspace_id INTEGER NOT NULL,
        body TEXT NOT NULL,
        created_by TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(workspace_id) REFERENCES pursuit_workspaces(workspace_id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS pursuit_workspace_questions(
        question_id INTEGER PRIMARY KEY AUTOINCREMENT,
        workspace_id INTEGER NOT NULL,
        question TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'OPEN',
        source_ref TEXT,
        owner_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(workspace_id) REFERENCES pursuit_workspaces(workspace_id)
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pursuit_workspace_account ON pursuit_workspaces(account_id, opportunity_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pursuit_blocker_workspace ON pursuit_workspace_blockers(workspace_id, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pursuit_note_workspace ON pursuit_workspace_notes(workspace_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pursuit_question_workspace ON pursuit_workspace_questions(workspace_id, status)")


def _opportunity(conn, opportunity_id: int):
    return conn.execute("SELECT id, source, external_id, title, buyer, country, value, deadline, publication_date, url FROM tenders WHERE id=?", (opportunity_id,)).fetchone()


def create_workspace(conn, account_id: str, opportunity_id: int, *, clock=None) -> dict:
    ensure_workspace_tables(conn)
    if _opportunity(conn, opportunity_id) is None:
        raise LookupError("opportunity_not_found")
    existing = get_workspace(conn, account_id, opportunity_id)
    if existing:
        return existing
    now = _now(clock)
    try:
        conn.execute("""INSERT INTO pursuit_workspaces(
            account_id, opportunity_id, workspace_status, review_state, submission_state, created_at, updated_at
        ) VALUES (?, ?, 'ACTIVE', 'NOT_REVIEWED', 'NOT_STARTED', ?, ?)""", (account_id, opportunity_id, now, now))
        conn.commit()
    except Exception:
        conn.rollback()
        existing = get_workspace(conn, account_id, opportunity_id)
        if existing:
            return existing
        raise
    return get_workspace(conn, account_id, opportunity_id)


def get_workspace(conn, account_id: str, opportunity_id: int) -> dict | None:
    ensure_workspace_tables(conn)
    row = conn.execute("SELECT * FROM pursuit_workspaces WHERE account_id=? AND opportunity_id=?", (account_id, opportunity_id)).fetchone()
    return dict(row) if row else None


def update_workspace(conn, account_id: str, opportunity_id: int, changes: Mapping, *, actor_subject: str | None, clock=None) -> dict:
    workspace = get_workspace(conn, account_id, opportunity_id)
    if not workspace:
        raise LookupError("workspace_not_found")
    allowed = {"workspace_status", "review_state", "submission_state", "owner_id"}
    if set(changes) - allowed:
        raise ValueError("unsupported_workspace_field")
    normalized = dict(changes)
    if "workspace_status" in normalized and normalized["workspace_status"] not in WORKSPACE_STATUSES:
        raise ValueError("invalid_workspace_status")
    if "review_state" in normalized and normalized["review_state"] not in REVIEW_STATES:
        raise ValueError("invalid_review_state")
    if "submission_state" in normalized and normalized["submission_state"] not in SUBMISSION_STATES:
        raise ValueError("invalid_submission_state")
    if "owner_id" in normalized:
        owner = normalized["owner_id"]
        if owner is not None and (not actor_subject or owner != actor_subject):
            raise PermissionError("owner_not_in_account")
    if not normalized:
        return workspace
    normalized["updated_at"] = _now(clock)
    assignments = ", ".join(f"{key}=?" for key in normalized)
    conn.execute(f"UPDATE pursuit_workspaces SET {assignments} WHERE account_id=? AND opportunity_id=?", (*normalized.values(), account_id, opportunity_id))
    conn.commit()
    return get_workspace(conn, account_id, opportunity_id)


def add_blocker(conn, account_id: str, opportunity_id: int, title: str, *, severity=None, actor_subject=None, clock=None) -> dict:
    workspace = get_workspace(conn, account_id, opportunity_id)
    title = str(title or "").strip()
    if not workspace:
        raise LookupError("workspace_not_found")
    if not title or len(title) > MAX_TITLE:
        raise ValueError("invalid_blocker_title")
    now = _now(clock)
    cur = conn.execute("INSERT INTO pursuit_workspace_blockers(workspace_id,title,status,severity,created_by,created_at) VALUES (?,?,'OPEN',?,?,?)", (workspace["workspace_id"], title, severity, actor_subject, now))
    conn.commit()
    return dict(conn.execute("SELECT * FROM pursuit_workspace_blockers WHERE blocker_id=?", (cur.lastrowid,)).fetchone())


def resolve_blocker(conn, account_id: str, opportunity_id: int, blocker_id: int, *, clock=None) -> dict:
    workspace = get_workspace(conn, account_id, opportunity_id)
    if not workspace:
        raise LookupError("workspace_not_found")
    now = _now(clock)
    cur = conn.execute("UPDATE pursuit_workspace_blockers SET status='RESOLVED', resolved_at=? WHERE blocker_id=? AND workspace_id=?", (now, blocker_id, workspace["workspace_id"]))
    if not cur.rowcount:
        raise LookupError("blocker_not_found")
    conn.commit()
    return dict(conn.execute("SELECT * FROM pursuit_workspace_blockers WHERE blocker_id=?", (blocker_id,)).fetchone())


def add_note(conn, account_id: str, opportunity_id: int, body: str, *, actor_subject=None, clock=None) -> dict:
    workspace = get_workspace(conn, account_id, opportunity_id)
    body = str(body or "").strip()
    if not workspace:
        raise LookupError("workspace_not_found")
    if not body or len(body) > MAX_NOTE:
        raise ValueError("invalid_note")
    cur = conn.execute("INSERT INTO pursuit_workspace_notes(workspace_id,body,created_by,created_at) VALUES (?,?,?,?)", (workspace["workspace_id"], body, actor_subject, _now(clock)))
    conn.commit()
    return dict(conn.execute("SELECT * FROM pursuit_workspace_notes WHERE note_id=?", (cur.lastrowid,)).fetchone())


def add_question(conn, account_id: str, opportunity_id: int, question: str, *, source_ref=None, owner_id=None, actor_subject=None, clock=None) -> dict:
    workspace = get_workspace(conn, account_id, opportunity_id)
    question = str(question or "").strip()
    if not workspace:
        raise LookupError("workspace_not_found")
    if not question or len(question) > MAX_QUESTION:
        raise ValueError("invalid_question")
    if owner_id is not None and (not actor_subject or owner_id != actor_subject):
        raise PermissionError("owner_not_in_account")
    now = _now(clock)
    cur = conn.execute("INSERT INTO pursuit_workspace_questions(workspace_id,question,status,source_ref,owner_id,created_at,updated_at) VALUES (?,?,'OPEN',?,?,?,?)", (workspace["workspace_id"], question, source_ref, owner_id, now, now))
    conn.commit()
    return dict(conn.execute("SELECT * FROM pursuit_workspace_questions WHERE question_id=?", (cur.lastrowid,)).fetchone())


def _provider_section(registry: ProviderRegistry, name: str, account_id: str, opportunity_id: int) -> dict:
    provider = registry.get(name)
    if provider is None:
        return {"status": "UNAVAILABLE"}
    try:
        summary = provider.summary(account_id=account_id, opportunity_id=opportunity_id)
        return {"status": "AVAILABLE", "data": dict(summary)}
    except Exception:
        return {"status": "FAILED"}


def workspace_view(conn, account_id: str, opportunity_id: int, *, providers: ProviderRegistry = EMPTY_PROVIDERS) -> dict:
    workspace = get_workspace(conn, account_id, opportunity_id)
    if not workspace:
        raise LookupError("workspace_not_found")
    opportunity = _opportunity(conn, opportunity_id)
    if opportunity is None:
        raise LookupError("opportunity_not_found")
    wid = workspace["workspace_id"]
    blockers = [dict(r) for r in conn.execute("SELECT * FROM pursuit_workspace_blockers WHERE workspace_id=? ORDER BY status, created_at DESC", (wid,)).fetchall()]
    notes = [dict(r) for r in conn.execute("SELECT * FROM pursuit_workspace_notes WHERE workspace_id=? ORDER BY created_at DESC", (wid,)).fetchall()]
    questions = [dict(r) for r in conn.execute("SELECT * FROM pursuit_workspace_questions WHERE workspace_id=? ORDER BY status, created_at DESC", (wid,)).fetchall()]
    sections = {name: _provider_section(providers, name, account_id, opportunity_id) for name in OPTIONAL_SECTIONS}
    return {
        "workspace": workspace,
        "opportunity": dict(opportunity),
        "blockers": blockers,
        "notes": notes,
        "questions": questions,
        "sections": sections,
        "missing_capabilities": [name for name, value in sections.items() if value["status"] != "AVAILABLE"],
    }
