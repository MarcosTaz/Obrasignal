import http.client
import json
import stat
import threading
from pathlib import Path
import pytest
from factory_cloud.control_tower_service import ControlTowerConfigurationError, make_server

def request(port,method,path,body=None,headers=None):
    conn=http.client.HTTPConnection('127.0.0.1',port,timeout=5);encoded=None if body is None else json.dumps(body).encode();h=dict(headers or {})
    if encoded is not None:h.setdefault('content-type','application/json');h.setdefault('content-length',str(len(encoded)))
    conn.request(method,path,body=encoded,headers=h);resp=conn.getresponse();raw=resp.read().decode();result=(resp.status,json.loads(raw) if raw else None,resp.getheader('access-control-allow-origin'));conn.close();return result

def running(tmp_path:Path,environ=None):
    server=make_server('127.0.0.1',0,environ=environ or {},runtime_dir=tmp_path);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();return server,thread,server.server_address[1]

def test_health_and_dispatch_boundary(tmp_path:Path):
    server,thread,port=running(tmp_path)
    try:
        assert request(port,'GET','/health')[0]==200
        ready_status,ready,_=request(port,'GET','/ready');assert ready_status==503;assert ready['ready'] is False;assert ready['portfolio_runtime']=='NOT_PROVISIONED'
        status,batch,_=request(port,'POST','/v1/dispatch',{'scope':'all'});assert status==202;assert batch['batch_id'];assert batch['items'];assert all('chat_url' not in item for item in batch['items'])
    finally:server.shutdown();thread.join(timeout=5);server.server_close()

def test_ready_requires_an_existing_executable_worker(tmp_path:Path):
    unavailable,thread,port=running(tmp_path,{'FACTORY_CLOUD_PORTFOLIO_WORKER':'/opt/shared-worker'})
    try:
        status,payload,_=request(port,'GET','/ready');assert status==503;assert payload['ready'] is False;assert payload['portfolio_runtime']=='EXECUTABLE_UNAVAILABLE'
    finally:unavailable.shutdown();thread.join(timeout=5);unavailable.server_close()

    worker=tmp_path/'worker';worker.write_text('#!/bin/sh\necho "{}"\n',encoding='utf-8');worker.chmod(worker.stat().st_mode|stat.S_IXUSR)
    server,thread,port=running(tmp_path,{'FACTORY_CLOUD_PORTFOLIO_WORKER':str(worker)})
    try:
        status,payload,_=request(port,'GET','/ready');assert status==200;assert payload['ready'] is True;assert payload['portfolio_runtime']=='EXECUTABLE_READY'
    finally:server.shutdown();thread.join(timeout=5);server.server_close()

def test_remote_endpoint_is_configured_but_not_claimed_ready_before_probe(tmp_path:Path):
    server,thread,port=running(tmp_path,{'FACTORY_CLOUD_PORTFOLIO_WORKER_ENDPOINT':'https://worker.example.test/v1/execute','FACTORY_CLOUD_PORTFOLIO_WORKER_TOKEN':'worker-secret'})
    try:
        status,payload,_=request(port,'GET','/ready');assert status==503;assert payload['ready'] is False;assert payload['portfolio_runtime']=='ENDPOINT_CONFIGURED_UNVERIFIED'
    finally:server.shutdown();thread.join(timeout=5);server.server_close()

def test_token_and_origin_are_fail_closed(tmp_path:Path):
    origin='https://founder.example.test';server,thread,port=running(tmp_path,{'FACTORY_CONTROL_TOKEN':'secret','FACTORY_CONTROL_ALLOWED_ORIGIN':origin})
    try:
        assert request(port,'POST','/v1/dispatch',{'scope':'all'})[0]==401
        assert request(port,'POST','/v1/dispatch',{'scope':'all'},{'authorization':'Bearer secret','origin':'https://evil.test'})[0]==403
        status,_,allow=request(port,'POST','/v1/dispatch',{'scope':'all'},{'authorization':'Bearer secret','origin':origin});assert status==202;assert allow==origin;assert allow!='*'
    finally:server.shutdown();thread.join(timeout=5);server.server_close()

def test_non_local_bind_requires_control_token_before_server_starts(tmp_path:Path):
    with pytest.raises(ControlTowerConfigurationError):make_server('0.0.0.0',0,environ={},runtime_dir=tmp_path)
    server=make_server('0.0.0.0',0,environ={'FACTORY_CONTROL_TOKEN':'secret'},runtime_dir=tmp_path);server.server_close()
