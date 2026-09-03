"""Server-authoritative user-to-company membership resolution.

This module deliberately does not infer tenancy from email/domain, request payloads,
query parameters, or headers. Production identity can opt into this authority only
when an explicit membership database is configured.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_SUBJECT_RE = re.compile(r"^[^\x00-\x1f\x7f]{1,255}$")
_ALLOWED_ROLES = {"admin", "member"}


class MembershipAuthorityError(RuntimeError):
    """Membership authority is absent, invalid, or does not authorize the actor."""


@dataclass(frozen=True)
class AccountMembership:
    subject: str
    account_id: str
    role: str


def install_membership_schema(conn: sqlite3.Connection) -> None:
    """Install the bounded membership schema for an explicit migration/test path."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS account_memberships(
            subject TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','member')),
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_account_memberships_account_active "
        "ON account_memberships(account_id, active)"
    )
    conn.commit()


def _validate_subject(subject: str) -> str:
    value = (subject or "").strip()
    if not _SUBJECT_RE.fullmatch(value):
        raise MembershipAuthorityError("invalid authenticated subject")
    return value


def _validate_account(account_id: str) -> str:
    value = (account_id or "").strip()
    if not _ACCOUNT_RE.fullmatch(value):
        raise MembershipAuthorityError("invalid membership account")
    return value


def resolve_membership(database_path: str, subject: str) -> AccountMembership:
    """Resolve an active membership or fail closed.

    The caller supplies only the already-verified provider subject. Tenant identity
    is read from server-side storage; caller-controlled account identifiers are not
    accepted by this function.
    """
    actor = _validate_subject(subject)
    path = (database_path or "").strip()
    if not path:
        raise MembershipAuthorityError("membership database is not configured")
    if path != ":memory:" and not Path(path).exists():
        raise MembershipAuthorityError("membership database is unavailable")

    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """
                SELECT subject, account_id, role
                FROM account_memberships
                WHERE subject=? AND active=1
                """,
                (actor,),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise MembershipAuthorityError("membership authority is unavailable") from exc

    if row is None:
        raise MembershipAuthorityError("active account membership required")
    account_id = _validate_account(row["account_id"])
    role = str(row["role"] or "").strip().lower()
    if role not in _ALLOWED_ROLES:
        raise MembershipAuthorityError("invalid membership role")
    return AccountMembership(subject=actor, account_id=account_id, role=role)
