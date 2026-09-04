from __future__ import annotations

import os

from .application import create_completion_app
from .auth import provider_tenant_resolver
from .repository import CapacityRepository

# Stable seam for provider-runtime construction and test injection. The completion
# app remains the implementation; the alias avoids coupling callers to its name.
create_app = create_completion_app


def create_provider_app(*, db_path: str | None = None):
    """Create the provider-authenticated Capacity Commitment application.

    There is no development-auth fallback. A durable database path is required
    either explicitly or through CAPACITY_COMMITMENT_DB_PATH.
    """

    resolved = (db_path or os.getenv("CAPACITY_COMMITMENT_DB_PATH") or "").strip()
    if not resolved:
        raise RuntimeError("CAPACITY_COMMITMENT_DB_PATH is required")
    repository = CapacityRepository(resolved)
    return create_app(repository, provider_tenant_resolver)
