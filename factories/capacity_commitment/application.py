from __future__ import annotations

from .completion_web import register_completion_routes
from .csv_import_web import register_csv_import_routes
from .evidence_commit_web import register_evidence_commit_routes
from .evidence_graph_web import register_evidence_graph_routes
from .repository import CapacityRepository
from .service_web import register_service_routes
from .web import TenantResolver, create_app


def create_completion_app(repository: CapacityRepository, tenant_resolver: TenantResolver):
    """Compose the proven assisted core with the complete customer workflow."""

    app = create_app(repository, tenant_resolver)
    register_completion_routes(app, repository)
    register_csv_import_routes(app, repository)
    register_evidence_commit_routes(app, repository)
    register_evidence_graph_routes(app, repository)
    register_service_routes(app, repository)
    return app
