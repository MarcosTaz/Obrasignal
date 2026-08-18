"""Identity context for ObraSignal API requests."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from flask import request
from jwt import InvalidTokenError

from auth_context_jwt import production_verifier


_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_ALLOWED_AUTH_MODES = {"development", "provider"}


@dataclass(frozen=True)
class RequestIdentity:
    account_id: str
    authenticated: bool
    subject: str | None = None
    claims: dict | None = None


def _valid_account(account_id: str) -> str:
    account_id = (account_id or "").strip()
    if not _ACCOUNT_RE.fullmatch(account_id):
        raise RuntimeError("Invalid account identity")
    return account_id


def configured_identity() -> RequestIdentity:
    """Resolve the request identity from development config or a verified JWT."""
    auth_mode = (os.getenv("OBRASIGNAL_AUTH_MODE") or "development").strip().lower()
    if auth_mode not in _ALLOWED_AUTH_MODES:
        raise RuntimeError("Invalid OBRASIGNAL_AUTH_MODE")

    if auth_mode == "development":
        account_id = _valid_account(os.getenv("OBRASIGNAL_ACCOUNT_ID") or "default")
        return RequestIdentity(account_id=account_id, authenticated=False)

    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise InvalidTokenError("Bearer token required")

    identity = production_verifier().verify(token.strip())
    account_id = _valid_account(identity.account_id)
    return RequestIdentity(
        account_id=account_id,
        authenticated=True,
        subject=identity.subject,
        claims=identity.claims,
    )
