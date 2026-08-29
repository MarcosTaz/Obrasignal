from factory_cloud.factory_switchboard import load_switchboard
from factory_cloud.global_control_tower import all_routes, dispatch_plan, select_routes, validate_registry_has_no_manual_chat_paths

def test_every_factory_gets_unique_internal_route_without_manual_chat_url():
    registry=load_switchboard();validate_registry_has_no_manual_chat_paths(registry);routes=all_routes(registry)
    assert len(routes)==len(registry['factories']);assert len({r.route for r in routes})==len(routes);assert len({r.worker_key for r in routes})==len(routes);assert all(r.route.startswith(('factory://','factory-cloud://')) for r in routes)

def test_obrasignal_scope_includes_parent_and_subfactories():
    registry=load_switchboard();routes=all_routes(registry);scope=select_routes(routes,'obrasignal');expected=[f for f in registry['factories'] if f['id']=='obrasignal' or f.get('group')=='obrasignal'];assert len(scope)==len(expected);assert all(r.factory_id=='obrasignal' or r.parent_id=='obrasignal' for r in scope)

def test_global_plan_separates_route_from_execution_truth():
    registry=load_switchboard();plan=dispatch_plan(registry,'all');assert plan['manual_chat_urls_required'] is False;assert plan['selected']==len(registry['factories']);assert plan['routable_now']>=2;assert plan['waiting_runtime']>=1;assert plan['routable_now']+plan['waiting_runtime']==plan['selected']

def test_business_factories_fail_closed_until_worker_exists():
    by_id={r.factory_id:r for r in all_routes(load_switchboard())};industrial=by_id['industrial-claims'];assert industrial.route=='factory://portfolio/industrial-claims';assert industrial.execution_state=='WAIT_RUNTIME';assert industrial.blocker=='portfolio_factory_worker_not_provisioned'

def test_recent_portfolio_factories_are_registered_and_get_automatic_routes():
    required={'change-exposure','contractcredit','debtrecover','royaltyrecover','gridrecover','govmargin','dealrecover','guaranteerelease'};routes={r.factory_id:r for r in all_routes(load_switchboard())};assert required.issubset(routes)
    for factory_id in required:
        route=routes[factory_id];assert route.route==f'factory://portfolio/{factory_id}';assert route.worker_key==f'portfolio:{factory_id}';assert route.execution_state=='WAIT_RUNTIME'

def test_historical_changeledger_scope_routes_once_to_scopeledger():
    registry=load_switchboard();plan=dispatch_plan(registry,'changeledger');assert plan['canonical_scope']=='scopeledger';assert plan['selected']==1;assert plan['routes'][0]['factory_id']=='scopeledger';assert all(route.factory_id!='changeledger' for route in all_routes(registry))
