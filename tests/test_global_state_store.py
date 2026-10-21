from pathlib import Path
from factory_cloud.global_state_store import GlobalStateStore

def routes():
    return [
        {'factory_id':'a','route':'factory://portfolio/a','worker_key':'portfolio:a'},
        {'factory_id':'b','route':'factory://portfolio/b','worker_key':'portfolio:b'},
    ]

def test_batch_persists_independent_item_results(tmp_path:Path):
    store=GlobalStateStore(tmp_path/'global.sqlite3');batch=store.create_batch('all',routes());state=store.batch(batch);assert state['state']=='QUEUED';assert len(state['items'])==2
    store.update_item(batch,'a','DONE',result={'status':'DONE','factory_id':'a'});mid=store.batch(batch);assert mid['state']=='RUNNING'
    store.update_item(batch,'b','WAIT',blocker='runtime_missing',result={'status':'WAIT','factory_id':'b'});final=store.batch(batch);assert final['state']=='PARTIAL';by_id={i['factory_id']:i for i in final['items']};assert by_id['a']['state']=='DONE';assert by_id['b']['state']=='WAIT';assert by_id['b']['blocker']=='runtime_missing'

def test_all_wait_or_blocked_marks_batch_blocked(tmp_path:Path):
    store=GlobalStateStore(tmp_path/'global.sqlite3');batch=store.create_batch('all',routes());store.update_item(batch,'a','WAIT');store.update_item(batch,'b','BLOCKED');assert store.batch(batch)['state']=='BLOCKED'
