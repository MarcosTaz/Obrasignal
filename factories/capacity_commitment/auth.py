from __future__ import annotations

from typing import Optional

from auth_context import configured_identity


def provider_tenant_resolver(_request) -> Optional[str]:
    """Resolve a Capacity Commitment tenant from verified ObraSignal identity.

    Capacity Commitment deliberately rejects the repository's development
    identity because it is not authenticated. Pilot/runtime access therefore
    requires the existing provider-mode JWT verification path.
    """

    identity = configured_identity()
    if not identity.authenticated:
        return None
    account_id = (identity.account_id or "").strip()
    if not account_id:
        return None
    return account_id
