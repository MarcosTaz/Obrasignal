from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

from factory_cloud.factory_switchboard import REGISTRY_PATH, canonical_factory_id, load_switchboard

class GlobalControlTowerError(RuntimeError): pass

@dataclass(frozen=True)
class ExecutionRoute:
    factory_id:str; parent_id:str|None; group:str; runtime:str; worker_key:str; route:str; signal:str; execution_state:str; blocker:str|None=None

def _signal(factory:dict[str,Any],registry:dict[str,Any])->str:return str(factory.get('signal') or registry.get('default_signal') or 'X')

def parent_for(factory:dict[str,Any])->str|None:
    factory_id=str(factory['id']);group=str(factory.get('group') or '')
    if factory_id=='factory-cloud':return None
    if factory_id=='obrasignal':return 'factory-cloud'
    if group=='obrasignal':return 'obrasignal'
    return 'factory-cloud'

def derive_route(factory:dict[str,Any],registry:dict[str,Any])->ExecutionRoute:
    factory_id=str(factory['id']);group=str(factory.get('group') or 'business');signal=_signal(factory,registry);parent_id=parent_for(factory)
    if factory_id=='factory-cloud':return ExecutionRoute(factory_id,parent_id,group,'factory_cloud_control_plane','control:factory-cloud','factory-cloud://control-plane',signal,'ROUTABLE')
    if factory_id=='obrasignal':return ExecutionRoute(factory_id,parent_id,group,'factory_cloud_app_worker','app:obrasignal','factory-cloud://apps/obrasignal',signal,'ROUTABLE')
    if group=='obrasignal':return ExecutionRoute(factory_id,parent_id,group,'portfolio_factory_worker',f'obrasignal:{factory_id}',f'factory://obrasignal/{factory_id}',signal,'WAIT_RUNTIME','portfolio_factory_worker_not_provisioned')
    return ExecutionRoute(factory_id,parent_id,group,'portfolio_factory_worker',f'portfolio:{factory_id}',f'factory://portfolio/{factory_id}',signal,'WAIT_RUNTIME','portfolio_factory_worker_not_provisioned')

def all_routes(registry:dict[str,Any])->list[ExecutionRoute]:
    routes=[derive_route(factory,registry) for factory in registry.get('factories',[])];values=[r.route for r in routes];keys=[r.worker_key for r in routes]
    if len(values)!=len(set(values)):raise GlobalControlTowerError('derived execution routes must be unique')
    if len(keys)!=len(set(keys)):raise GlobalControlTowerError('derived worker keys must be unique')
    return routes

def select_routes(routes:Iterable[ExecutionRoute],scope:str,aliases:dict[str,str]|None=None)->list[ExecutionRoute]:
    routes=list(routes);normalized=scope.strip().lower()
    if normalized in {'all','todas','global'}:return routes
    if normalized in {'obrasignal','os','obrasignal+subs'}:return [r for r in routes if r.factory_id=='obrasignal' or r.parent_id=='obrasignal']
    if normalized in {'obrasignal-subs','os-subs','subs'}:return [r for r in routes if r.parent_id=='obrasignal']
    if normalized in {'business','negocios','negócios'}:return [r for r in routes if r.group in {'business','developing','specialist'}]
    if normalized in {'development','desenvolvimento','apps'}:return [r for r in routes if r.runtime in {'factory_cloud_control_plane','factory_cloud_app_worker'}]
    canonical=(aliases or {}).get(scope,scope);selected=[r for r in routes if r.factory_id==canonical]
    if not selected:raise GlobalControlTowerError(f'unknown scope or factory: {scope}')
    return selected

def dispatch_plan(registry:dict[str,Any],scope:str='all')->dict[str,Any]:
    canonical=canonical_factory_id(scope,registry) if scope in (registry.get('aliases') or {}) else scope
    selected=select_routes(all_routes(registry),canonical,registry.get('aliases') or {});routable=[r for r in selected if r.execution_state=='ROUTABLE'];waiting=[r for r in selected if r.execution_state!='ROUTABLE']
    return {'scope':scope,'canonical_scope':canonical,'manual_chat_urls_required':False,'selected':len(selected),'routable_now':len(routable),'waiting_runtime':len(waiting),'routes':[asdict(r) for r in selected]}

def validate_registry_has_no_manual_chat_paths(registry:dict[str,Any])->None:
    forbidden={'chat_url','conversation_url','chatgpt_url','manual_url'}
    for factory in registry.get('factories',[]):
        found=forbidden.intersection(factory)
        if found:raise GlobalControlTowerError(f"manual chat routing is forbidden for {factory.get('id')}: {sorted(found)}")

def main()->int:
    parser=argparse.ArgumentParser(description='Global Factory Control Tower deterministic router');parser.add_argument('--scope',default='all');parser.add_argument('--registry',type=Path,default=REGISTRY_PATH);args=parser.parse_args();registry=load_switchboard(args.registry);validate_registry_has_no_manual_chat_paths(registry);print(json.dumps(dispatch_plan(registry,args.scope),indent=2,ensure_ascii=False));return 0

if __name__=='__main__':raise SystemExit(main())
