from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from factory_cloud.global_app_executor import FactoryCloudRouteExecutor
from factory_cloud.global_dispatcher import GlobalDispatcher
from factory_cloud.portfolio_worker import PortfolioFactoryWorker


DEFAULT_RUNTIME_DIR = Path(".factory_cloud")


def _absolute_or_default(env: Mapping[str, str], key: str, default: Path) -> Path:
    raw = str(env.get(key) or "").strip()
    if not raw:
        return default
    path = Path(raw)
    if not path.is_absolute():
        raise ValueError(f"{key} must be an absolute path")
    return path


def build_global_dispatcher(
    environ: Mapping[str, str] | None = None,
    *,
    runtime_dir: Path | None = None,
) -> GlobalDispatcher:
    """Build the whole Control Tower from one host configuration.

    No per-Factory paths are accepted. The host may override two shared durable
    state files and one shared portfolio-worker executable through environment
    variables. Factory routes themselves always come from the canonical registry.
    """
    env = dict(os.environ if environ is None else environ)
    root = runtime_dir or DEFAULT_RUNTIME_DIR
    global_state = _absolute_or_default(
        env,
        "FACTORY_CLOUD_GLOBAL_STATE",
        root / "global-control-tower.sqlite3",
    )
    app_state = _absolute_or_default(
        env,
        "FACTORY_CLOUD_APP_STATE",
        root / "factory-cloud-apps.sqlite3",
    )
    app_bridge = FactoryCloudRouteExecutor(app_state)
    portfolio_worker = PortfolioFactoryWorker(environ=env)
    return GlobalDispatcher(
        global_state,
        control_executor=app_bridge.execute_control,
        app_executor=app_bridge.execute_app,
        portfolio_worker=portfolio_worker,
    )
