import http.client
import json
import stat
import subprocess
import threading
from pathlib import Path
import pytest
from factory_cloud.portfolio_agent_service import PortfolioAgentConfigurationError, execute_agent_request, make_agent_server

def payload():return {'factory_id':'scopeledger','route':'factory://portfolio/scopeledger','signal':'X','mission':'resume','baton':{'active':'validate','resume_at':'validate'}}

def test_missing_agent_executor_waits_without_inventing_execution():
    result=execute_agent_request(payload(),environ={});assert result['status']=='WAIT';assert result['blockers']==['portfolio_agent_executor_not_provisioned'];assert result['resume_at']=='validate'

def test_agent_executor_cannot_spoof_identity(tmp_path:Path):
    exe=tmp_path/'agent';exe.write_text('#!/bin/sh\nexit 0\n');exe.chmod(exe.stat().st_mode|stat.S_IXUSR)
    def runner(argv,**kwargs):return subprocess.CompletedProcess(argv,0,stdout=json.dumps({'status':'DONE','factory_id':'other'}),stderr='')
    result=execute_agent_request(payload(),environ={'FACTORY_PORTFOLIO_AGENT_EXECUTOR':str(exe)},runner=runner);assert result['status']=='ERROR';assert result['error']['type']=='AGENT_IDENTITY_MISMATCH'

def test_agent_service_requires_one_host_token():
    with pytest.raises(PortfolioAgentConfigurationError):make_agent_server(environ={})

def test_http_agent_boundary_returns_wait_until_real_executor_exists(tmp_path:Path):
    server=make_agent_server('127.0.0.1',0,environ={'FACTORY_PORTFOLIO_AGENT_TOKEN':'secret'});thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();port=server.server_address[1]
    try:
        conn=http.client.HTTPConnection('127.0.0.1',port,timeout=5);raw=json.dumps(payload()).encode();conn.request('POST','/v1/execute',body=raw,headers={'content-type':'application/json','content-length':str(len(raw)),'authorization':'Bearer secret'});resp=conn.getresponse();body=json.loads(resp.read());conn.close();assert resp.status==200;assert body['status']=='WAIT';assert body['factory_id']=='scopeledger'
    finally:server.shutdown();thread.join(timeout=5);server.server_close()
