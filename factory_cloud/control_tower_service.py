from __future__ import annotations

import argparse
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from factory_cloud.control_tower_api import handle_request
from factory_cloud.global_runtime import build_global_dispatcher, runtime_readiness

MAX_BODY_BYTES=64*1024
LOCAL_BIND_HOSTS={"127.0.0.1","localhost","::1"}

class ControlTowerConfigurationError(RuntimeError): pass

class ControlTowerHTTPHandler(BaseHTTPRequestHandler):
    dispatcher=None; auth_token:str|None=None; allowed_origin:str|None=None; runtime_status:dict[str,object]={}; server_version='FactoryControlTower/0.4'
    def log_message(self,format:str,*args:Any)->None:return
    def _origin_allowed(self)->bool:
        origin=str(self.headers.get('origin') or '').strip()
        if not origin:return True
        return bool(self.allowed_origin and hmac.compare_digest(origin,self.allowed_origin))
    def _authorized(self)->bool:
        if not self.auth_token:return True
        return hmac.compare_digest(str(self.headers.get('authorization') or ''),f'Bearer {self.auth_token}')
    def _send(self,status:int,payload:dict[str,Any])->None:
        data=json.dumps(payload,ensure_ascii=False,sort_keys=True).encode('utf-8'); self.send_response(status)
        self.send_header('content-type','application/json; charset=utf-8'); self.send_header('cache-control','no-store'); self.send_header('x-content-type-options','nosniff'); self.send_header('x-frame-options','DENY')
        if self.allowed_origin and self._origin_allowed(): self.send_header('access-control-allow-origin',self.allowed_origin); self.send_header('vary','Origin')
        self.send_header('content-length',str(len(data))); self.end_headers()
        if self.command!='HEAD': self.wfile.write(data)
    def _path(self)->str:return urlsplit(self.path).path
    def _guard_api(self)->bool:
        if not self._origin_allowed():self._send(403,{'error':'origin_not_allowed'});return False
        if not self._authorized():self._send(401,{'error':'unauthorized'});return False
        return True
    def _json_body(self):
        raw_length=self.headers.get('content-length')
        if raw_length is None:return True,{}
        try:length=int(raw_length)
        except ValueError:return False,None
        if length<0 or length>MAX_BODY_BYTES:return False,None
        raw=self.rfile.read(length)
        if not raw:return True,{}
        try:payload=json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError,json.JSONDecodeError):return False,None
        return (True,payload) if isinstance(payload,dict) else (False,None)
    def do_OPTIONS(self)->None:
        if not self._origin_allowed():self._send(403,{'error':'origin_not_allowed'});return
        self.send_response(204)
        if self.allowed_origin:self.send_header('access-control-allow-origin',self.allowed_origin);self.send_header('vary','Origin')
        self.send_header('access-control-allow-methods','GET,POST,OPTIONS');self.send_header('access-control-allow-headers','authorization,content-type');self.send_header('access-control-max-age','600');self.send_header('cache-control','no-store');self.end_headers()
    def do_GET(self)->None:
        path=self._path()
        if path=='/health':self._send(200,{'ok':True,'service':'global-control-tower'});return
        if path=='/ready':
            payload=dict(self.runtime_status);payload['service']='global-control-tower';self._send(200 if payload.get('ready') is True else 503,payload);return
        if not self._guard_api():return
        status,payload=handle_request(self.dispatcher,method='GET',path=path);self._send(status,payload)
    def do_POST(self)->None:
        if not self._guard_api():return
        valid,body=self._json_body()
        if not valid:self._send(400,{'error':'invalid_json_body'});return
        status,payload=handle_request(self.dispatcher,method='POST',path=self._path(),body=body);self._send(status,payload)

def _validate_bind_security(host:str, token:str|None)->None:
    normalized=str(host or '').strip().lower()
    if normalized not in LOCAL_BIND_HOSTS and not token:raise ControlTowerConfigurationError('non-local Control Tower bind requires FACTORY_CONTROL_TOKEN')

def make_server(host:str,port:int,*,environ:dict[str,str]|None=None,runtime_dir:Path|None=None)->ThreadingHTTPServer:
    env=dict(os.environ if environ is None else environ);token=str(env.get('FACTORY_CONTROL_TOKEN') or '').strip() or None;origin=str(env.get('FACTORY_CONTROL_ALLOWED_ORIGIN') or '').strip() or None
    _validate_bind_security(host,token);dispatcher=build_global_dispatcher(environ=env,runtime_dir=runtime_dir);readiness=runtime_readiness(env)
    handler=type('BoundControlTowerHTTPHandler',(ControlTowerHTTPHandler,),{'dispatcher':dispatcher,'auth_token':token,'allowed_origin':origin,'runtime_status':readiness});return ThreadingHTTPServer((host,port),handler)

def main()->int:
    parser=argparse.ArgumentParser(description='Persistent Global Factory Control Tower service');parser.add_argument('--host',default=os.environ.get('FACTORY_CONTROL_HOST','127.0.0.1'));parser.add_argument('--port',type=int,default=int(os.environ.get('FACTORY_CONTROL_PORT','8787')));parser.add_argument('--runtime-dir',type=Path,default=None);args=parser.parse_args()
    if args.port<1 or args.port>65535:parser.error('port must be between 1 and 65535')
    try:server=make_server(args.host,args.port,runtime_dir=args.runtime_dir)
    except ControlTowerConfigurationError as exc:parser.error(str(exc))
    try:server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:pass
    finally:server.server_close()
    return 0

if __name__=='__main__':raise SystemExit(main())
