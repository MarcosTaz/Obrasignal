from copy import deepcopy

import pytest

from factory_cloud.control_plane import RegistryError, load_registry, validate_registry
from factory_cloud.portfolio import load_portfolio, portfolio_index


def test_verified_source_apps_are_registered_read_only_until_adapter_exists():
    registry = load_registry()
    apps = {app["app_id"]: app for app in registry["applications"]}
    expected = {
        "guaranteerelease": ("factory/guaranteerelease", "46fea6901e85f753b52c611456640fd4e4b23490", "ventures/guaranteerelease"),
        "royaltyrecover": ("royaltyrecover/company-web-app", "673e4a292c9cea6e6813786d75021d3267df3911", "factories/royaltyrecover"),
    }
    for app_id, (branch, head, path) in expected.items():
        app = apps[app_id]
        assert app["activation"] == {"enabled": True, "mode": "read_only_until_adapter_verified", "priority": app["activation"]["priority"]}
        assert app["source_truth"]["verified"] is True
        assert app["source_truth"]["canonical_branch"] == branch
        assert app["source_truth"]["canonical_head"] == head
        assert app["source_truth"]["application_path"] == path
        assert "execution_adapter" not in app
        assert "task_capabilities" not in app

    portfolio = portfolio_index(load_portfolio())
    assert portfolio["guaranteerelease"]["source_status"] == "registered_read_only"
    assert portfolio["royaltyrecover"]["source_status"] == "registered_read_only"


def test_adapter_wait_mode_rejects_unverified_or_incomplete_source():
    registry = load_registry()
    for app_id in ("guaranteerelease", "royaltyrecover"):
        bad = deepcopy(registry)
        app = next(item for item in bad["applications"] if item["app_id"] == app_id)
        app["source_truth"]["verified"] = False
        with pytest.raises(RegistryError, match="explicitly verified"):
            validate_registry(bad)

        bad = deepcopy(registry)
        app = next(item for item in bad["applications"] if item["app_id"] == app_id)
        app["execution_adapter"] = {"configured": True}
        with pytest.raises(RegistryError, match="read-only app cannot declare"):
            validate_registry(bad)
