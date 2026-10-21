from __future__ import annotations

from typing import Any
from factory_cloud.factory_switchboard import load_switchboard
from factory_cloud.global_control_tower import dispatch_plan, validate_registry_has_no_manual_chat_paths
from factory_cloud.global_dispatcher import GlobalDispatcher

def handle_request(dispatcher:GlobalDispatcher,*,method:str,path:str,body:dict[str,Any]|None=None)->tuple[int,dict[str,Any]]:
    method=method.upper().strip()
    if method=='GET' and path=='/v1/routes':
        try:
            registry=load_switchboard();validate_registry_has_no_manual_chat_paths(registry);plan=dispatch_plan(registry,'all')
        except Exception as exc:return 500,{'error':'route_manifest_unavailable','type':type(exc).__name__}
        return 200,{'manual_chat_urls_required':False,'aliases':dict(registry.get('aliases') or {}),'selected':plan['selected'],'routes':plan['routes']}
    if method=='POST' and path=='/v1/dispatch':
        payload=body or {}
        if not isinstance(payload,dict):return 400,{'error':'body_must_be_object'}
        scope=str(payload.get('scope') or 'all').strip() or 'all'
        try:batch=dispatcher.dispatch(scope)
        except Exception as exc:return 400,{'error':'dispatch_rejected','type':type(exc).__name__}
        return 202,batch
    prefix='/v1/batches/'
    if method=='GET' and path.startswith(prefix):
        batch_id=path[len(prefix):].strip()
        if not batch_id or '/' in batch_id:return 400,{'error':'invalid_batch_id'}
        try:batch=dispatcher.store.batch(batch_id)
        except KeyError:return 404,{'error':'batch_not_found'}
        return 200,batch
    return 404,{'error':'not_found'}
