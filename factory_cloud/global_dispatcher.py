from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from factory_cloud.factory_switchboard import load_switchboard
from factory_cloud.global_control_tower import all_routes, select_routes
from factory_cloud.global_state_store import GlobalStateStore
from factory_cloud.portfolio_worker import PortfolioExecutionRequest, PortfolioFactoryWorker


Result = dict[str, Any]
Executor = Callable[[dict[str, Any]], Result]


class GlobalDispatcher:
    """Dispatch one founder command across independent Factory routes.

    The dispatcher persists the batch before executing anything. Every Factory item
    is isolated: WAIT/BLOCKED/ERROR for one route never prevents another route from
    being attempted. Execution truth is taken only from executor results.
    """

    def __init__(
        self,
        state_path: Path | str,
        *,
        control_executor: Executor | None = None,
        app_executor: Executor | None = None,
        portfolio_worker: PortfolioFactoryWorker | None = None,
    ) -> None:
        self.store = GlobalStateStore(state_path)
        self.control_executor = control_executor
        self.app_executor = app_executor
        self.portfolio_worker = portfolio_worker or PortfolioFactoryWorker()

    @staticmethod
    def _baton(factory: dict[str, Any]) -> dict[str, Any]:
        return {
            "mission": str(factory.get("mission") or factory.get("target") or factory.get("name") or ""),
            "active": str(factory.get("active") or "resume_existing_factory"),
            "next": list(factory.get("next") or []),
            "wait": list(factory.get("wait") or []),
            "resume_at": str(factory.get("resume_at") or factory.get("active") or "resume_existing_factory"),
        }

    @staticmethod
    def _normalize_result(result: Result, factory_id: str, route: str) -> Result:
        if not isinstance(result, dict):
            return {
                "status": "ERROR",
                "factory_id": factory_id,
                "route": route,
                "blockers": ["executor_returned_non_object"],
            }
        status = str(result.get("status") or "").upper()
        if status not in {"DONE", "WAIT", "BLOCKED", "ERROR"}:
            return {
                "status": "ERROR",
                "factory_id": factory_id,
                "route": route,
                "blockers": ["executor_returned_invalid_status"],
            }
        normalized = dict(result)
        normalized["status"] = status
        normalized.setdefault("factory_id", factory_id)
        normalized.setdefault("route", route)
        return normalized

    def _execute(self, route: Any, factory: dict[str, Any]) -> Result:
        request = {
            "factory_id": route.factory_id,
            "route": route.route,
            "worker_key": route.worker_key,
            "signal": route.signal,
            "baton": self._baton(factory),
        }
        if route.runtime == "factory_cloud_control_plane":
            if self.control_executor is None:
                return {
                    "status": "WAIT",
                    "factory_id": route.factory_id,
                    "route": route.route,
                    "blockers": ["factory_cloud_control_executor_not_wired"],
                    "resume_at": request["baton"]["resume_at"],
                }
            return self._normalize_result(self.control_executor(request), route.factory_id, route.route)
        if route.runtime == "factory_cloud_app_worker":
            if self.app_executor is None:
                return {
                    "status": "WAIT",
                    "factory_id": route.factory_id,
                    "route": route.route,
                    "blockers": ["factory_cloud_app_executor_not_wired"],
                    "resume_at": request["baton"]["resume_at"],
                }
            return self._normalize_result(self.app_executor(request), route.factory_id, route.route)

        portfolio_request = PortfolioExecutionRequest(
            factory_id=route.factory_id,
            route=route.route,
            signal=route.signal,
            mission=request["baton"]["mission"],
            baton=request["baton"],
        )
        return self._normalize_result(
            self.portfolio_worker.execute(portfolio_request), route.factory_id, route.route
        )

    def dispatch(self, scope: str = "all") -> dict[str, Any]:
        registry = load_switchboard()
        factories = {str(item["id"]): item for item in registry.get("factories", [])}
        routes = select_routes(all_routes(registry), scope)
        batch_id = self.store.create_batch(scope, [asdict(route) for route in routes])

        for route in routes:
            factory = factories[route.factory_id]
            self.store.update_item(batch_id, route.factory_id, "RUNNING")
            try:
                result = self._execute(route, factory)
            except Exception as exc:  # fail closed at the route boundary
                result = {
                    "status": "ERROR",
                    "factory_id": route.factory_id,
                    "route": route.route,
                    "blockers": ["global_dispatch_executor_exception"],
                    "error": {"type": type(exc).__name__},
                    "resume_at": self._baton(factory)["resume_at"],
                }
            status = result["status"]
            blockers = result.get("blockers") or []
            blocker = str(blockers[0]) if blockers else None
            self.store.update_item(
                batch_id,
                route.factory_id,
                status,
                blocker=blocker,
                result=result,
            )

        return self.store.batch(batch_id)
