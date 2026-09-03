from __future__ import annotations

from pathlib import Path
from typing import Any

from factory_cloud.adapters import AdapterRegistry
from factory_cloud.control_plane import load_registry
from factory_cloud.orchestrator import PersistentFactoryOrchestrator
from factory_cloud.state_store import StateStore


class FactoryCloudRouteExecutor:
    """Bridge Global Control Tower routes to the existing durable app orchestrator."""

    def __init__(self,state_path:Path|str,*,adapters:AdapterRegistry|None=None)->None:
        registry=load_registry()
        self.orchestrator=PersistentFactoryOrchestrator(registry,StateStore(state_path),adapters=adapters,recover_interrupted=True)

    @staticmethod
    def _result(status:str,**extra:Any)->dict[str,Any]:
        payload={"status":status,"blockers":[]}; payload.update(extra); return payload

    def execute_control(self,request:dict[str,Any])->dict[str,Any]:
        cycle=self.orchestrator.run_cycle(max_dispatches=100); dispatches=list(cycle.get("dispatches") or []); blockers=cycle.get("blockers") or {}
        if dispatches and all(item.get("status")=="DONE" for item in dispatches): return self._result("DONE",evidence={"dispatches":dispatches,"global_state":cycle.get("global_state")})
        if any(item.get("status")=="ERROR" for item in dispatches): return self._result("ERROR",evidence={"dispatches":dispatches,"global_state":cycle.get("global_state")},blockers=["factory_cloud_cycle_error"])
        return self._result("WAIT",evidence={"dispatches":dispatches,"global_state":cycle.get("global_state")},blockers=["factory_cloud_cycle_waiting"] if blockers or not dispatches else [])

    def execute_app(self,request:dict[str,Any])->dict[str,Any]:
        app_id=str(request.get("factory_id") or "").strip(); state=self.orchestrator.store.get_app(app_id)
        if state is None:return self._result("BLOCKED",blockers=["app_not_registered_in_factory_cloud"])
        decision=self.orchestrator._decision_for(state)
        if decision is None:return self._result("WAIT",evidence={"app_state":state.get("state"),"resume_at":state.get("resume_at")},blockers=list(state.get("blockers") or []) or ["app_has_no_eligible_work"])
        result=self.orchestrator.execute_one(decision)
        return {"status":result.status,"evidence":result.evidence,"blockers":list(result.blockers),"resume_at":result.resume_at or decision.task,"factory_id":app_id,"route":request.get("route")}
