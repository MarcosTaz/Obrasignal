from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

import requests

ALLOWED_RESULT_STATUSES={"DONE","WAIT","BLOCKED","ERROR"}
LOCAL_HOSTS={"127.0.0.1","localhost","::1"}

class PortfolioWorkerError(RuntimeError): pass

@dataclass(frozen=True)
class PortfolioExecutionRequest:
    factory_id:str; route:str; signal:str; mission:str; baton:dict[str,Any]
    def payload(self)->dict[str,Any]: return {"factory_id":self.factory_id,"route":self.route,"signal":self.signal,"mission":self.mission,"baton":self.baton}
    def to_json(self)->str: return json.dumps(self.payload(),ensure_ascii=False,sort_keys=True)

def configured_executor(environ:dict[str,str]|None=None)->Path|None:
    env=os.environ if environ is None else environ; raw=str(env.get("FACTORY_CLOUD_PORTFOLIO_WORKER") or "").strip()
    if not raw:return None
    path=Path(raw)
    if not path.is_absolute(): raise PortfolioWorkerError("FACTORY_CLOUD_PORTFOLIO_WORKER must be an absolute executable path")
    return path

def configured_endpoint(environ:dict[str,str]|None=None)->str|None:
    env=os.environ if environ is None else environ; raw=str(env.get("FACTORY_CLOUD_PORTFOLIO_WORKER_ENDPOINT") or "").strip()
    if not raw:return None
    parsed=urlsplit(raw)
    if parsed.scheme not in {"https","http"} or not parsed.netloc: raise PortfolioWorkerError("FACTORY_CLOUD_PORTFOLIO_WORKER_ENDPOINT must be an absolute HTTP(S) URL")
    if parsed.scheme=="http" and parsed.hostname not in LOCAL_HOSTS: raise PortfolioWorkerError("remote portfolio worker endpoint must use HTTPS")
    if parsed.username or parsed.password: raise PortfolioWorkerError("portfolio worker endpoint credentials must not be embedded in URL")
    return raw.rstrip("/")

def _base_result(request:PortfolioExecutionRequest)->dict[str,Any]: return {"factory_id":request.factory_id,"route":request.route,"resume_at":request.baton.get("resume_at") or request.baton.get("active")}

class PortfolioFactoryWorker:
    def __init__(self,*,environ:dict[str,str]|None=None,runner:Callable[...,subprocess.CompletedProcess[str]]=subprocess.run,poster:Callable[...,Any]=requests.post,timeout_seconds:int=1800)->None:
        self.environ=dict(os.environ if environ is None else environ); self.runner=runner; self.poster=poster; self.timeout_seconds=timeout_seconds
    def _configuration(self):
        try: executable=configured_executor(self.environ); endpoint=configured_endpoint(self.environ)
        except PortfolioWorkerError as exc:return {"status":"BLOCKED","blockers":["portfolio_worker_configuration_invalid"],"error":{"type":"INVALID_WORKER_CONFIGURATION","detail":str(exc)}}
        if executable is not None and endpoint is not None:return {"status":"BLOCKED","blockers":["portfolio_worker_configuration_ambiguous"],"error":{"type":"AMBIGUOUS_WORKER_CONFIGURATION"}}
        if endpoint is not None:
            parsed=urlsplit(endpoint); token=str(self.environ.get("FACTORY_CLOUD_PORTFOLIO_WORKER_TOKEN") or "").strip()
            if parsed.hostname not in LOCAL_HOSTS and not token:return {"status":"BLOCKED","blockers":["portfolio_worker_token_required"],"error":{"type":"REMOTE_WORKER_TOKEN_REQUIRED"}}
        return executable,endpoint
    def execute(self,request:PortfolioExecutionRequest)->dict[str,Any]:
        config=self._configuration()
        if isinstance(config,dict): return {**_base_result(request),**config}
        executable,endpoint=config
        if endpoint is not None:return self._execute_endpoint(request,endpoint)
        if executable is not None:return self._execute_executable(request,executable)
        return {**_base_result(request),"status":"WAIT","blockers":["portfolio_factory_worker_not_provisioned"]}
    def _execute_endpoint(self,request,endpoint):
        headers={"content-type":"application/json","accept":"application/json"}; token=str(self.environ.get("FACTORY_CLOUD_PORTFOLIO_WORKER_TOKEN") or "").strip()
        if token:headers["authorization"]=f"Bearer {token}"
        try:response=self.poster(endpoint,json=request.payload(),headers=headers,timeout=self.timeout_seconds,allow_redirects=False)
        except Exception:return {**_base_result(request),"status":"ERROR","blockers":["portfolio_factory_worker_endpoint_failed"],"error":{"type":"WORKER_ENDPOINT_FAILED"}}
        if not 200<=int(response.status_code)<300:return {**_base_result(request),"status":"ERROR","blockers":["portfolio_factory_worker_endpoint_non_success"],"error":{"type":"WORKER_ENDPOINT_NON_SUCCESS","code":int(response.status_code)}}
        try:payload=response.json()
        except (ValueError,json.JSONDecodeError):return self._invalid_result(request)
        return self._validated_payload(request,payload)
    def _execute_executable(self,request,executable):
        try:completed=self.runner([str(executable)],input=request.to_json(),text=True,capture_output=True,timeout=self.timeout_seconds,check=False,env=self.environ)
        except (OSError,subprocess.SubprocessError):return {**_base_result(request),"status":"ERROR","blockers":["portfolio_factory_worker_execution_failed"],"error":{"type":"WORKER_EXECUTION_FAILED"}}
        if completed.returncode!=0:return {**_base_result(request),"status":"ERROR","blockers":["portfolio_factory_worker_nonzero_exit"],"error":{"type":"WORKER_NONZERO_EXIT","code":completed.returncode}}
        try:payload=json.loads(completed.stdout or "")
        except json.JSONDecodeError:return self._invalid_result(request)
        return self._validated_payload(request,payload)
    def _invalid_result(self,request,detail=None):
        error={"type":"INVALID_WORKER_RESULT"}
        if detail:error["detail"]=detail
        return {**_base_result(request),"status":"ERROR","blockers":["portfolio_factory_worker_invalid_result"],"error":error}
    def _validated_payload(self,request,payload):
        if not isinstance(payload,dict):return self._invalid_result(request)
        status=str(payload.get("status") or "")
        if status not in ALLOWED_RESULT_STATUSES:return self._invalid_result(request,"unsupported status")
        if payload.get("factory_id") is not None and str(payload["factory_id"])!=request.factory_id:return self._invalid_result(request,"factory identity mismatch")
        if payload.get("route") is not None and str(payload["route"])!=request.route:return self._invalid_result(request,"route identity mismatch")
        payload["factory_id"]=request.factory_id; payload["route"]=request.route; payload.setdefault("resume_at",request.baton.get("resume_at") or request.baton.get("active")); return payload
