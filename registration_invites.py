"""ObraSignal invitation authority. Isolated from CERTACTUM and any identity provider.

Not an authentication provider: issue/consume must be called only by trusted backend
code. No public HTTP endpoint, admin bearer token, or client-held signing secret.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

_EMAIL = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,189}$")
_CODE = re.compile(r"^OS-[0-9a-f]{48}$")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS obrasignal_registration_invites (
 id TEXT PRIMARY KEY,
 email TEXT NOT NULL,
 code_digest BLOB NOT NULL UNIQUE,
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 expires_at TEXT NOT NULL,
 used_at TEXT,
 revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS obrasignal_invites_email_idx
 ON obrasignal_registration_invites(email, expires_at);
"""

def _utcnow():
    return datetime.now(timezone.utc)

def _email(raw: str) -> str:
    normalized = str(raw or "").strip().lower()
    if len(normalized) > 254 or not _EMAIL.fullmatch(normalized):
        raise ValueError("invalid_invitation_email")
    return normalized

def _when(at: datetime | None) -> datetime:
    current = at or _utcnow()
    if current.tzinfo is None:
        raise ValueError("naive_datetime_forbidden")
    return current.astimezone(timezone.utc)

def _stamp(t: datetime) -> str:
    return t.isoformat(timespec="microseconds")

def init_invites(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)

def issue_invite(conn: sqlite3.Connection, *, email: str, created_by: str,
                 hours: int = 72, now: datetime | None = None) -> dict:
    if not isinstance(hours, int) or isinstance(hours, bool) or not (1 <= hours <= 168):
        raise ValueError("invalid_invitation_lifetime")
    actor = str(created_by or "").strip()
    if not actor or len(actor) > 128:
        raise ValueError("invalid_issuer")
    recipient = _email(email)
    issued = _when(now)
    expires = issued + timedelta(hours=hours)
    code = "OS-" + secrets.token_hex(24)
    digest = hashlib.sha256(code.encode("ascii")).digest()
    identifier = secrets.token_hex(16)
    # Callers must never return this code from an unauthenticated route.
    with conn:
        conn.execute(
            "UPDATE obrasignal_registration_invites SET revoked_at=? "
            "WHERE email=? AND used_at IS NULL AND revoked_at IS NULL",
            (_stamp(issued), recipient),
        )
        conn.execute(
            "INSERT INTO obrasignal_registration_invites "
            "(id,email,code_digest,created_by,created_at,expires_at) "
            "VALUES (?,?,?,?,?,?)",
            (identifier, recipient, digest, actor, _stamp(issued), _stamp(expires)),
        )
    return {"id": identifier, "email": recipient, "code": code,
            "expires_at": _stamp(expires)}

def consume_invite(conn: sqlite3.Connection, *, email: str, code: str,
                   now: datetime | None = None) -> bool:
    recipient = _email(email)
    if not isinstance(code, str) or not _CODE.fullmatch(code):
        return False
    digest = hashlib.sha256(code.encode("ascii")).digest()
    time = _stamp(_when(now))
    # UPDATE is atomic; only one concurrent signup can change used_at from NULL.
    with conn:
        cur = conn.execute(
            "UPDATE obrasignal_registration_invites SET used_at=? "
            "WHERE email=? AND code_digest=? AND used_at IS NULL "
            "AND revoked_at IS NULL AND expires_at>?",
            (time, recipient, digest, time),
        )
    return cur.rowcount == 1

def revoke_invite(conn: sqlite3.Connection, *, identifier: str,
                  now: datetime | None = None) -> bool:
    if not re.fullmatch(r"[0-9a-f]{32}", str(identifier or "")):
        return False
    with conn:
        cur = conn.execute(
            "UPDATE obrasignal_registration_invites SET revoked_at=? "
            "WHERE id=? AND used_at IS NULL AND revoked_at IS NULL",
            (_stamp(_when(now)), identifier),
        )
    return cur.rowcount == 1
