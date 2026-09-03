from pathlib import Path
from factory_cloud.control_tower_api import handle_request
from factory_cloud.global_dispatcher import GlobalDispatcher
from factory_cloud.portfolio_worker import PortfolioFactoryWorker

class DoneWorker(PortfolioFactoryWorker):
    def __init__(self): pass
    def execute(self,request): return {'status':'DONE','factory_id':request.factory_id,'route':request.route}

def dispatcher(tmp_path:Path):
    return GlobalDispatcher(tmp_path/'global.sqlite3',control_executor=lambda request:{'status':'DONE'},app_executor=lambda request:{'status':'DONE'},portfolio_worker=DoneWorker())

def test_route_manifest_has_automatic_unique_routes_and_no_manual_chat_urls(tmp_path:Path):
    status,payload=handle_request(dispatcher(tmp_path),method='GET',path='/v1/routes')
    assert status==200;assert payload['manual_chat_urls_required'] is False;assert payload['routes'];assert payload['selected']==len(payload['routes'])
    routes=[item['route'] for item in payload['routes']];assert len(routes)==len(set(routes));assert all('chat' not in route.lower() for route in routes)
    assert payload['aliases']['changeledger']=='scopeledger'

def test_dispatch_and_batch_read_contract(tmp_path:Path):
    d=dispatcher(tmp_path);status,batch=handle_request(d,method='POST',path='/v1/dispatch',body={'scope':'business'});assert status==202;assert batch['items']
    read_status,loaded=handle_request(d,method='GET',path=f"/v1/batches/{batch['batch_id']}");assert read_status==200;assert loaded['batch_id']==batch['batch_id']
