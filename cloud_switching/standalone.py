from __future__ import annotations

from pathlib import Path
from typing import Callable

from flask import Flask

from .auth import resolve_canonical_tenant
from .integration import register_cloud_switching


def create_app(
    *,
    database_path: str | Path,
    resolve_tenant: Callable[[], str | None] = resolve_canonical_tenant,
) -> Flask:
    app = Flask("cloud_switching_pilot")
    register_cloud_switching(
        app,
        database_path=str(database_path),
        resolve_tenant=resolve_tenant,
    )
    return app
