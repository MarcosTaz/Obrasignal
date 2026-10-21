from factory_cloud.factory_switchboard import load_switchboard
from factory_cloud.global_control_tower import (
    all_routes,
    dispatch_plan,
    select_routes,
    validate_registry_has_no_manual_chat_paths,
)


def test_every_factory_gets_unique_internal_route_without_manual_chat_url():
    registry = load_switchboard()
    validate_registry_has_no_manual_chat_paths(registry)
    routes = all_routes(registry)

    assert len(routes) == len(registry["factories"])
    assert len({route.route for route in routes}) == len(routes)
    assert len({route.worker_key for route in routes}) == len(routes)
    assert all(route.route.startswith(("factory://", "factory-cloud://")) for route in routes)


def test_obrasignal_scope_includes_parent_and_all_subfactories():
    registry = load_switchboard()
    routes = all_routes(registry)
    os_scope = select_routes(routes, "obrasignal")

    expected = [
        factory
        for factory in registry["factories"]
        if factory["id"] == "obrasignal" or factory.get("group") == "obrasignal"
    ]
    assert len(os_scope) == len(expected)
    assert os_scope[0].factory_id == "obrasignal"
    assert all(route.factory_id == "obrasignal" or route.parent_id == "obrasignal" for route in os_scope)


def test_obrasignal_subfactory_scope_excludes_parent():
    registry = load_switchboard()
    routes = all_routes(registry)
    subs = select_routes(routes, "obrasignal-subs")

    assert subs
    assert all(route.parent_id == "obrasignal" for route in subs)
    assert all(route.factory_id != "obrasignal" for route in subs)


def test_global_plan_reports_execution_truth_separately_from_routing():
    registry = load_switchboard()
    plan = dispatch_plan(registry, "all")

    assert plan["manual_chat_urls_required"] is False
    assert plan["selected"] == len(registry["factories"])
    assert plan["routable_now"] >= 2
    assert plan["waiting_runtime"] >= 1
    assert plan["routable_now"] + plan["waiting_runtime"] == plan["selected"]


def test_obrasignal_and_factory_cloud_are_real_current_runtime_routes():
    registry = load_switchboard()
    by_id = {route.factory_id: route for route in all_routes(registry)}

    assert by_id["factory-cloud"].runtime == "factory_cloud_control_plane"
    assert by_id["factory-cloud"].execution_state == "ROUTABLE"
    assert by_id["obrasignal"].runtime == "factory_cloud_app_worker"
    assert by_id["obrasignal"].execution_state == "ROUTABLE"


def test_business_factories_fail_closed_until_portfolio_worker_exists():
    registry = load_switchboard()
    by_id = {route.factory_id: route for route in all_routes(registry)}

    industrial = by_id["industrial-claims"]
    assert industrial.route == "factory://portfolio/industrial-claims"
    assert industrial.execution_state == "WAIT_RUNTIME"
    assert industrial.blocker == "portfolio_factory_worker_not_provisioned"
