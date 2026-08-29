from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from factory_cloud.global_app_executor import FactoryCloudRouteExecutor
from factory_cloud.global_dispatcher import GlobalDispatcher
from factory_cloud.portfolio_worker import LOCAL_HOSTS, PortfolioFactoryWorker, PortfolioWorkerError, configured_endpoint, configured_executor

DEFAULT_RUNTIME_DIR=Path('.factory_cloud')

def _absolute_or_default(env:Mapping[str,str],key:str,default:Path)->Path:
    raw=str(env.get(key) or '').strip()
    if not raw:return default
    path=Path(raw)
    if not path.is_absolute():raise ValueError(f'{key} must be an absolute path')
    return path

def runtime_readiness(environ:Mapping[str,str]|None=None)->dict[str,object]:
    env=dict(os.environ if environ is None else environ)
    try:
        executable=configured_executor(env);endpoint=configured_endpoint(env)
    except PortfolioWorkerError:
        return {'ready':False,'portfolio_runtime':'INVALID','blockers':['portfolio_worker_configuration_invalid']}
    if executable is not None and endpoint is not None:
        return {'ready':False,'portfolio_runtime':'AMBIGUOUS','blockers':['portfolio_worker_configuration_ambiguous']}
    if endpoint is not None:
        host=urlsplit(endpoint).hostname
        token=bool(str(env.get('FACTORY_CLOUD_PORTFOLIO_WORKER_TOKEN') or '').strip())
        if host not in LOCAL_HOSTS and not token:
            return {'ready':False,'portfolio_runtime':'ENDPOINT_BLOCKED','blockers':['portfolio_worker_token_required']}
        return {'ready':False,'portfolio_runtime':'ENDPOINT_CONFIGURED_UNVERIFIED','blockers':['portfolio_worker_endpoint_unverified']}
    if executable is not None:
        if not executable.is_file() or not os.access(executable,os.X_OK):
            return {'ready':False,'portfolio_runtime':'EXECUTABLE_UNAVAILABLE','blockers':['portfolio_worker_executable_unavailable']}
        return {'ready':True,'portfolio_runtime':'EXECUTABLE_READY','blockers':[]}
    return {'ready':False,'portfolio_runtime':'NOT_PROVISIONED','blockers':['portfolio_factory_worker_not_provisioned']}

def build_global_dispatcher(environ:Mapping[str,str]|None=None,*,runtime_dir:Path|None=None)->GlobalDispatcher:
    env=dict(os.environ if environ is None else environ); root=runtime_dir or DEFAULT_RUNTIME_DIR
    global_state=_absolute_or_default(env,'FACTORY_CLOUD_GLOBAL_STATE',root/'global-control-tower.sqlite3')
    app_state=_absolute_or_default(env,'FACTORY_CLOUD_APP_STATE',root/'factory-cloud-apps.sqlite3')
    app_bridge=FactoryCloudRouteExecutor(app_state); portfolio_worker=PortfolioFactoryWorker(environ=env)
    return GlobalDispatcher(global_state,control_executor=app_bridge.execute_control,app_executor=app_bridge.execute_app,portfolio_worker=portfolio_worker)

def main()->int:
    parser=argparse.ArgumentParser(description='One-command Global Factory Control Tower')
    parser.add_argument('scope',nargs='?',default='all',help='all, obrasignal, obrasignal-subs, business, development, or one factory_id')
    parser.add_argument('--runtime-dir',type=Path,default=DEFAULT_RUNTIME_DIR)
    parser.add_argument('--readiness',action='store_true')
    args=parser.parse_args()
    if args.readiness:
        print(json.dumps(runtime_readiness(),ensure_ascii=False,indent=2,sort_keys=True));return 0
    try: result=build_global_dispatcher(runtime_dir=args.runtime_dir).dispatch(args.scope)
    except (OSError,ValueError,RuntimeError) as exc: parser.error(str(exc))
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)); return 0

if __name__=='__main__': raise SystemExit(main())
