from __future__ import annotations

import argparse
import hmac
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

MAX_BODY_BYTES=256*1024
ALLOWED_STATUSES={'DONE','WAIT','BLOCKED','ERROR'}

class PortfolioAgentConfigurationError(RuntimeError): pass

def configured_agent_executor(environ:dict[str,str]|None=None)->Path|None:
    env=os.environ if environ is None else environ;raw=str(env.get('FACTORY_PORTFOLIO_AGENT_EXECUTOR') or '').strip()
    if not raw:return None
    path=Path(raw)
    if not path.is_absolute():raise PortfolioAgentConfigurationError('FACTORY_PORTFOLIO_AGENT_EXECUTOR must be absolute')
    return path

def execute_agent_request(payload:dict[str,Any],*,environ:dict[str,str]|None=None,runner:Callable[...,subprocess.CompletedProcess[str]]=subprocess.run,timeout_seconds:int=1800)->dict[str,Any]:
    factory_id=str(payload.get('factory_id') or '').strip();route=str(payload.get('route') or '').strip();baton=payload.get('baton')
    if not factory_id or not route.startswith('factory://') or not isinstance(baton,dict):return {'status':'ERROR','factory_id':factory_id,'route':route,'blockers':['invalid_agent_request'],'error':{'type':'INVALID_AGENT_REQUEST'}}
    try:executor=configured_agent_executor(environ)
    except PortfolioAgentConfigurationError:return {'status':'BLOCKED','factory_id':factory_id,'route':route,'blockers':['portfolio_agent_configuration_invalid']}
    if executor is None or not executor.is_file() or not os.access(executor,os.X_OK):return {'status':'WAIT','factory_id':factory_id,'route':route,'blockers':['portfolio_agent_executor_not_provisioned'],'resume_at':baton.get('resume_at') or baton.get('active')}
    try:completed=runner([str(executor)],input=json.dumps(payload,ensure_ascii=False,sort_keys=True),text=True,capture_output=True,timeout=timeout_seconds,check=False,env=dict(os.environ if environ is None else environ))
    except (OSError,subprocess.SubprocessError):return {'status':'ERROR','factory_id':factory_id,'route':route,'blockers':['portfolio_agent_execution_failed'],'resume_at':baton.get('resume_at') or baton.get('active')}
    if completed.returncode!=0:return {'status':'ERROR','factory_id':factory_id,'route':route,'blockers':['portfolio_agent_nonzero_exit'],'error':{'type':'AGENT_NONZERO_EXIT','code':completed.returncode}}
    try:result=json.loads(completed.stdout or '')
    except json.JSONDecodeError:return {'status':'ERROR','factory_id':factory_id,'route':route,'blockers':['portfolio_agent_invalid_result'],'error':{'type':'INVALID_AGENT_RESULT'}}
    if not isinstance(result,dict) or str(result.get('status') or '') not in ALLOWED_STATUSES:return {'status':'ERROR','factory_id':factory_id,'route':route,'blockers':['portfolio_agent_invalid_result'],'error':{'type':'INVALID_AGENT_RESULT'}}
    if result.get('factory_id') is not None and str(result['factory_id'])!=factory_id:return {'status':'ERROR','factory_id':factory_id,'route':route,'blockers':['portfolio_agent_identity_mismatch'],'error':{'type':'AGENT_IDENTITY_MISMATCH'}}
    if result.get('route') is not None and str(result['route'])!=route:return {'status':'ERROR','factory_id':factory_id,'route':route,'blockers':['portfolio_agent_route_mismatch'],'error':{'type':'AGENT_ROUTE_MISMATCH'}}
    result['factory_id']=factory_id;result['route']=route;result.setdefault('resume_at',baton.get('resume_at') or baton.get('active'));return result

class PortfolioAgentHTTPHandler(BaseHTTPRequestHandler):
    environ:dict[str,str]={};auth_token:str|None=None;server_version='PortfolioAgentRuntime/0.2'
    def log_message(self,format:str,*args:Any)->None:return
    def _send(self,status:int,payload:dict[str,Any])->None:
        data=json.dumps(payload,ensure_ascii=False,sort_keys=True).encode();self.send_response(status);self.send_header('content-type','application/json; charset=utf-8');self.send_header('cache-control','no-store');self.send_header('x-content-type-options','nosniff');self.send_header('content-length',str(len(data)));self.end_headers();self.wfile.write(data)
    def _authorized(self)->bool:return bool(self.auth_token and hmac.compare_digest(str(self.headers.get('authorization') or ''),f'Bearer {self.auth_token}'))
    def do_GET(self)->None:
        path=urlsplit(self.path).path
        if path=='/health':self._send(200,{'ok':True,'service':'portfolio-agent-runtime'});return
        if path=='/ready':
            try:executor=configured_agent_executor(self.environ);ready=bool(executor and executor.is_file() and os.access(executor,os.X_OK))
            except PortfolioAgentConfigurationError:ready=False
            self._send(200 if ready else 503,{'ready':ready,'service':'portfolio-agent-runtime'});return
        self._send(404,{'error':'not_found'})
    def do_POST(self)->None:
        if urlsplit(self.path).path!='/v1/execute':self._send(404,{'error':'not_found'});return
        if not self._authorized():self._send(401,{'error':'unauthorized'});return
        try:length=int(self.headers.get('content-length') or '0')
        except ValueError:self._send(400,{'error':'invalid_content_length'});return
        if length<1 or length>MAX_BODY_BYTES:self._send(400,{'error':'invalid_body_size'});return
        try:payload=json.loads(self.rfile.read(length).decode())
        except (UnicodeDecodeError,json.JSONDecodeError):self._send(400,{'error':'invalid_json'});return
        if not isinstance(payload,dict):self._send(400,{'error':'body_must_be_object'});return
        self._send(200,execute_agent_request(payload,environ=self.environ))

def make_agent_server(host:str='127.0.0.1',port:int=8788,*,environ:dict[str,str]|None=None)->ThreadingHTTPServer:
    env=dict(os.environ if environ is None else environ);token=str(env.get('FACTORY_PORTFOLIO_AGENT_TOKEN') or '').strip()
    if not token:raise PortfolioAgentConfigurationError('FACTORY_PORTFOLIO_AGENT_TOKEN required')
    handler=type('BoundPortfolioAgentHTTPHandler',(PortfolioAgentHTTPHandler,),{'environ':env,'auth_token':token});return ThreadingHTTPServer((host,port),handler)

def main()->int:
    parser=argparse.ArgumentParser(description='Shared portfolio Factory agent runtime boundary');parser.add_argument('--host',default=os.environ.get('FACTORY_PORTFOLIO_AGENT_HOST','127.0.0.1'));parser.add_argument('--port',type=int,default=int(os.environ.get('FACTORY_PORTFOLIO_AGENT_PORT','8788')));args=parser.parse_args()
    try:server=make_agent_server(args.host,args.port)
    except PortfolioAgentConfigurationError as exc:parser.error(str(exc))
    try:server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:pass
    finally:server.server_close()
    return 0

if __name__=='__main__':raise SystemExit(main())
