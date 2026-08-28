from __future__ import annotations

from auth_context import configured_identity


def resolve_canonical_tenant() -> str:
    """Return the canonical ObraSignal account for the current request.

    In provider mode this value exists only after the canonical JWT verifier has
    accepted the bearer token. Development mode intentionally preserves the
    repository's existing configured-account behavior for local/synthetic use.
    """
    identity = configured_identity()
    return identity.account_id
