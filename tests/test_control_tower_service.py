import http.client
import json
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
        status,batch,_=request(port,'POST','/v1/dispatch',{'scope':'all'});assert status==202;assert batch['batch_id'];assert batch['items'];assert all('chat_url' not in item for item in batch['items'])
    finally:server.shutdown();thread.join(timeout=5);server.server_close()

def test_token_and_origin_are_fail_closed(tmp_path:Path):
    origin='https://founder.example.test';server,thread,port=running(tmp_path,{'FACTORY_CONTROL_TOKEN':'secret','FACTORY_CONTROL_ALLOWED_ORIGIN':origin})
    try:
        assert request(port,'POST','/v1/dispatch',{'scope':'all'})[0]==401
        assert request(port,'POST','/v1/dispatch',{'scope':'all'},{'authorization':'Bearer secret','origin':'https://evil.test'})[0]==403
        status,_,allow=request(port,'POST','/v1/dispatch',{'scope':'all'},{'authorization':'Bearer secret','origin':origin});assert status==202;assert allow==origin;assert allow!='*'
    finally:server.shutdown();thread.join(timeout=5);server.server_close()

def test_non_local_bind_requires_control_token_before_server_starts(tmp_path:Path):
    with pytest.raises(ControlTowerConfigurationError):
        make_server('0.0.0.0',0,environ={},runtime_dir=tmp_path)
    server=make_server('0.0.0.0',0,environ={'FACTORY_CONTROL_TOKEN':'secret'},runtime_dir=tmp_path)
    server.server_close()
