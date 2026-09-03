from pathlib import Path
from factory_cloud.global_dispatcher import GlobalDispatcher
from factory_cloud.portfolio_worker import PortfolioFactoryWorker

class FakeWorker(PortfolioFactoryWorker):
    def __init__(self): pass
    def execute(self,request):
        if request.factory_id=='industrial-claims': return {'status':'BLOCKED','factory_id':request.factory_id,'route':request.route,'blockers':['synthetic_block']}
        return {'status':'DONE','factory_id':request.factory_id,'route':request.route,'evidence':{'synthetic':True}}

def test_one_blocked_factory_does_not_stop_other_business_routes(tmp_path:Path):
    dispatcher=GlobalDispatcher(tmp_path/'global.sqlite3',portfolio_worker=FakeWorker())
    batch=dispatcher.dispatch('business');items={item['factory_id']:item for item in batch['items']}
    assert items['industrial-claims']['state']=='BLOCKED';assert any(item['state']=='DONE' for fid,item in items.items() if fid!='industrial-claims');assert batch['state']=='PARTIAL'

def test_executor_identity_mismatch_is_fail_closed(tmp_path:Path):
    dispatcher=GlobalDispatcher(tmp_path/'global.sqlite3',control_executor=lambda req:{'status':'DONE','factory_id':'spoofed'},app_executor=lambda req:{'status':'DONE'})
    batch=dispatcher.dispatch('development');by_id={i['factory_id']:i for i in batch['items']};assert by_id['factory-cloud']['state']=='ERROR'

def test_historical_alias_dispatches_only_canonical_factory(tmp_path:Path):
    dispatcher=GlobalDispatcher(tmp_path/'global.sqlite3',portfolio_worker=FakeWorker());batch=dispatcher.dispatch('changeledger')
    assert batch['requested_scope']=='changeledger';assert batch['canonical_scope']=='scopeledger';assert len(batch['items'])==1;assert batch['items'][0]['factory_id']=='scopeledger';assert batch['items'][0]['state']=='DONE'
