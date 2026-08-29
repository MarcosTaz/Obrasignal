import json
import subprocess
from factory_cloud.portfolio_worker import PortfolioExecutionRequest, PortfolioFactoryWorker

def request():
    return PortfolioExecutionRequest(factory_id='scopeledger',route='factory://portfolio/scopeledger',signal='X',mission='resume',baton={'active':'validate','resume_at':'validate'})

def test_missing_worker_waits_fail_closed():
    result=PortfolioFactoryWorker(environ={}).execute(request());assert result['status']=='WAIT';assert result['factory_id']=='scopeledger'

def test_remote_endpoint_requires_token():
    result=PortfolioFactoryWorker(environ={'FACTORY_CLOUD_PORTFOLIO_WORKER_ENDPOINT':'https://worker.example.test/v1/execute'}).execute(request());assert result['status']=='BLOCKED';assert result['error']['type']=='REMOTE_WORKER_TOKEN_REQUIRED'

def test_executable_receives_factory_identity_over_stdin():
    calls=[]
    def runner(argv,**kwargs):
        calls.append((argv,kwargs));return subprocess.CompletedProcess(argv,0,stdout=json.dumps({'status':'DONE'}),stderr='')
    result=PortfolioFactoryWorker(environ={'FACTORY_CLOUD_PORTFOLIO_WORKER':'/opt/worker'},runner=runner).execute(request());assert result['status']=='DONE';sent=json.loads(calls[0][1]['input']);assert sent['factory_id']=='scopeledger';assert sent['route']=='factory://portfolio/scopeledger'

def test_result_cannot_spoof_identity_or_running_state():
    def bad_identity(argv,**kwargs):return subprocess.CompletedProcess(argv,0,stdout=json.dumps({'status':'DONE','factory_id':'other'}),stderr='')
    result=PortfolioFactoryWorker(environ={'FACTORY_CLOUD_PORTFOLIO_WORKER':'/opt/worker'},runner=bad_identity).execute(request());assert result['status']=='ERROR';assert result['factory_id']=='scopeledger'
    def running(argv,**kwargs):return subprocess.CompletedProcess(argv,0,stdout=json.dumps({'status':'RUNNING'}),stderr='')
    result=PortfolioFactoryWorker(environ={'FACTORY_CLOUD_PORTFOLIO_WORKER':'/opt/worker'},runner=running).execute(request());assert result['status']=='ERROR'
