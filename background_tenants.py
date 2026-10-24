"""Resolve eligible tenant IDs for background jobs without a request identity.

Source ingestion runs outside Flask's request context. In provider mode a
missing account is *not* permission to fabricate a tenant; continue ingesting
public source data but skip private account-specific decision writes.
"""
from __future__ import annotations

import os


def eligible_background_accounts(conn, *, existing_accounts=None) -> list[str]:
    if existing_accounts is None:
        from account_registry import list_active_accounts

        existing_accounts = list_active_accounts(conn)
    if existing_accounts:
        return list(existing_accounts)

    mode = (os.getenv("OBRASIGNAL_AUTH_MODE") or "development").strip().lower()
    if mode == "provider":
        return []
    if mode == "development":
        # Preserve legacy local/demo workflow only outside provider mode.
        from auth_context import configured_identity

        return [configured_identity().account_id]
    raise RuntimeError("Invalid OBRASIGNAL_AUTH_MODE")
