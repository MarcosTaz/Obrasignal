import stat
import threading
from pathlib import Path

from factory_cloud.global_dispatcher import GlobalDispatcher
from factory_cloud.portfolio_agent_service import make_agent_server
from factory_cloud.portfolio_worker import PortfolioFactoryWorker


def _synthetic_agent(tmp_path: Path) -> Path:
    script = tmp_path / 'synthetic-portfolio-agent'
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json,sys\n"
        "p=json.load(sys.stdin)\n"
        "if p['factory_id']=='industrial-claims':\n"
        " print(json.dumps({'status':'BLOCKED','factory_id':p['factory_id'],'route':p['route'],'blockers':['synthetic_local_blocker']}))\n"
        "else:\n"
        " print(json.dumps({'status':'DONE','factory_id':p['factory_id'],'route':p['route'],'evidence':{'synthetic_http_agent':True}}))\n",
        encoding='utf-8',
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def test_one_command_reaches_all_business_factories_through_one_http_agent_and_survives_restart(tmp_path: Path):
    executor = _synthetic_agent(tmp_path)
    token = 'shared-agent-secret'
    server = make_agent_server(
        '127.0.0.1',
        0,
        environ={'FACTORY_PORTFOLIO_AGENT_TOKEN': token, 'FACTORY_PORTFOLIO_AGENT_EXECUTOR': str(executor)},
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = f"http://127.0.0.1:{server.server_address[1]}/v1/execute"
        worker = PortfolioFactoryWorker(
            environ={
                'FACTORY_CLOUD_PORTFOLIO_WORKER_ENDPOINT': endpoint,
                'FACTORY_CLOUD_PORTFOLIO_WORKER_TOKEN': token,
            }
        )
        state_path = tmp_path / 'global.sqlite3'
        dispatcher = GlobalDispatcher(state_path, portfolio_worker=worker)
        batch = dispatcher.dispatch('business')

        items = {item['factory_id']: item for item in batch['items']}
        assert len(items) > 10
        assert items['industrial-claims']['state'] == 'BLOCKED'
        assert all(item['state'] == 'DONE' for factory_id, item in items.items() if factory_id != 'industrial-claims')
        assert batch['state'] == 'PARTIAL'
        assert all('chat' not in item['route'].lower() for item in items.values())

        restarted = GlobalDispatcher(state_path, portfolio_worker=worker)
        recovered = restarted.store.batch(batch['batch_id'])
        assert recovered['state'] == 'PARTIAL'
        assert {item['factory_id'] for item in recovered['items']} == set(items)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
