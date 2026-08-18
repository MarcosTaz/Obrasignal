"""Identity context for API requests.

The current development mode uses a configured account id so the storage
boundary can be tested before a real authentication provider is introduced.
Clients must never choose account identity from request payloads.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass


_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


@dataclass(frozen=True)
class RequestIdentity:
    account_id: str
    authenticated: bool


def configured_identity() -> RequestIdentity:
    """Return the configured development identity.

    In production this function is an explicit seam for replacing the
    development identity with a real authenticated principal.
    """
    account_id = (os.getenv("OBRASIGNAL_ACCOUNT_ID") or "default").strip() or "default"
    if not _ACCOUNT_RE.fullmatch(account_id):
        raise RuntimeError("Invalid OBRASIGNAL_ACCOUNT_ID")
    authenticated = os.getenv("OBRASIGNAL_AUTH_MODE", "development").lower() != "development"
    return RequestIdentity(account_id=account_id, authenticated=authenticated)
