"""Identity context for ObraSignal API requests.

Development mode uses an explicit configured account id only for local/testing
purposes. It is never treated as authenticated. A production authentication
provider must supply a validated principal before an account is considered
authenticated.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass


_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_ALLOWED_AUTH_MODES = {"development", "provider"}


@dataclass(frozen=True)
class RequestIdentity:
    account_id: str
    authenticated: bool


def configured_identity() -> RequestIdentity:
    """Return the configured identity context.

    Development mode is deliberately unauthenticated. Selecting provider mode
    without a real validated provider is a configuration error rather than an
    implicit authentication success.
    """
    account_id = (os.getenv("OBRASIGNAL_ACCOUNT_ID") or "default").strip() or "default"
    if not _ACCOUNT_RE.fullmatch(account_id):
        raise RuntimeError("Invalid OBRASIGNAL_ACCOUNT_ID")

    auth_mode = (os.getenv("OBRASIGNAL_AUTH_MODE") or "development").strip().lower()
    if auth_mode not in _ALLOWED_AUTH_MODES:
        raise RuntimeError("Invalid OBRASIGNAL_AUTH_MODE")

    if auth_mode == "development":
        return RequestIdentity(account_id=account_id, authenticated=False)

    # The real provider must replace this seam before provider mode is enabled.
    raise RuntimeError("Production authentication provider is not configured")
