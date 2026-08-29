from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Mapping

from factory_cloud.control_plane import ACTIVATION_CODE
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
    """Build one global dispatcher without per-Factory paths.

    App/control execution uses the same private-queue runtime as the long-lived
    Factory Cloud worker. Portfolio Factories share exactly one optional worker
    executable; when it is absent those routes remain truthful WAITs while other
    routes continue.
    """
    env = dict(os.environ if environ is None else environ)
    root = runtime_dir or DEFAULT_RUNTIME_DIR
    global_state = _absolute_or_default(env, "FACTORY_CLOUD_GLOBAL_STATE", root / "global-control-tower.sqlite3")
    app_state = _absolute_or_default(env, "FACTORY_CLOUD_APP_STATE", root / "state.sqlite3")
    queue_dir = _absolute_or_default(env, "FACTORY_CLOUD_QUEUE_DIR", root / "queues")
    app_bridge = FactoryCloudRouteExecutor(app_state, queue_dir=queue_dir)
    portfolio_worker = PortfolioFactoryWorker(environ=env)
    return GlobalDispatcher(
        global_state,
        control_executor=app_bridge.execute_control,
        app_executor=app_bridge.execute_app,
        portfolio_worker=portfolio_worker,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Executable D Global Factory Control Tower")
    parser.add_argument("code", help="global Factory Cloud activation code; must be D")
    parser.add_argument(
        "scope",
        nargs="?",
        default="all",
        help="all, obrasignal, obrasignal-subs, business, development, or one factory_id",
    )
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    args = parser.parse_args()
    if args.code != ACTIVATION_CODE:
        parser.error("Global Factory Cloud activation requires D")
    try:
        dispatcher = build_global_dispatcher(runtime_dir=args.runtime_dir)
        result = dispatcher.dispatch(args.scope)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
