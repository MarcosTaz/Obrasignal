from factory_cloud.control_plane import load_registry
from factory_cloud.portfolio import load_portfolio, portfolio_index


def test_runtime_wait_recovery_apps_cannot_claim_g3():
    registry = load_registry()
    portfolio = portfolio_index(load_portfolio())
    for app in registry["applications"]:
        if (app.get("activation") or {}).get("mode") != "runtime_provisioning_wait":
            continue
        assert app["development_state"].endswith("RUNTIME_PROVISIONING_WAIT")
        assert portfolio[app["app_id"]]["maturity"] == "G2"
