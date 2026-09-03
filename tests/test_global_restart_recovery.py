from pathlib import Path
from factory_cloud.global_dispatcher import GlobalDispatcher
from factory_cloud.portfolio_worker import PortfolioFactoryWorker

class DoneWorker(PortfolioFactoryWorker):
    def __init__(self): pass
    def execute(self,request): return {'status':'DONE','factory_id':request.factory_id,'route':request.route,'evidence':{'worker':'synthetic'}}

def test_completed_batch_survives_dispatcher_restart(tmp_path:Path):
    state=tmp_path/'global.sqlite3';first=GlobalDispatcher(state,portfolio_worker=DoneWorker());batch=first.dispatch('business');batch_id=batch['batch_id'];assert batch['state']=='DONE'
    second=GlobalDispatcher(state,portfolio_worker=DoneWorker());loaded=second.store.batch(batch_id);assert loaded['state']=='DONE';assert loaded['items'];assert all(item['state']=='DONE' for item in loaded['items'])
