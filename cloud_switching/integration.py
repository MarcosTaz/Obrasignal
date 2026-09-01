from __future__ import annotations

from flask import Flask

from .auth import resolve_canonical_tenant
from .sqlite_workspace import SQLiteDecisionWorkspace
from .web import create_blueprint


def register_cloud_switching(
    app: Flask,
    *,
    database_path: str,
    resolve_tenant=resolve_canonical_tenant,
) -> None:
    """Install the cloud-switching pilot into the canonical Flask app exactly once.

    Production supplies the existing ObraSignal SQLite path and canonical identity
    resolver. Tests may inject an isolated database and resolver without weakening
    production identity boundaries.
    """
    if "cloud_switching" in app.blueprints:
        return
    workspace = SQLiteDecisionWorkspace(database_path)
    blueprint = create_blueprint(workspace=workspace, resolve_tenant=resolve_tenant)
    # Override the standalone blueprint prefix so production routes stay under the
    # existing /api/v1 CORS and API boundary.
    app.register_blueprint(blueprint, url_prefix="/api/v1/cloud-switching")
