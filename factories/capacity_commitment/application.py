from __future__ import annotations

from .completion_web import register_completion_routes
from .repository import CapacityRepository
from .web import TenantResolver, create_app


def create_completion_app(repository: CapacityRepository, tenant_resolver: TenantResolver):
    """Compose the proven assisted core with the completion customer workflow."""

    app = create_app(repository, tenant_resolver)
    register_completion_routes(app, repository)
    return app
