from __future__ import annotations

import os

from .auth import provider_tenant_resolver
from .repository import CapacityRepository
from .web import create_app


def create_provider_app(*, db_path: str | None = None):
    """Create the provider-authenticated assisted T1 application.

    There is no development-auth fallback. A durable database path is required
    either explicitly or through CAPACITY_COMMITMENT_DB_PATH.
    """

    resolved = (db_path or os.getenv("CAPACITY_COMMITMENT_DB_PATH") or "").strip()
    if not resolved:
        raise RuntimeError("CAPACITY_COMMITMENT_DB_PATH is required")
    repository = CapacityRepository(resolved)
    return create_app(repository, provider_tenant_resolver)
