import json

import pytest

from factory_cloud.portfolio import PortfolioError, load_portfolio, portfolio_index


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_canonical_portfolio_covers_switchboard():
    data = load_portfolio()
    index = portfolio_index(data)
    assert index["factory-cloud"]["layer"] == "control"
    assert index["contractcredit"]["source_status"] == "registered"
    assert index["aviation-lease-entitlement-recovery"]["source_status"] == "registered"


def test_missing_registered_factory_fails_closed(tmp_path):
    registry = tmp_path / "factories.json"
    portfolio = tmp_path / "portfolio.json"
    _write(registry, {"factories": [{"id": "known"}]})
    _write(portfolio, {"layers": [{"id": "verticals"}], "maturity_gates": [{"id": "G0"}], "portfolio": []})
    with pytest.raises(PortfolioError, match="missing portfolio mapping"):
        load_portfolio(portfolio, registry)


def test_phantom_registered_claim_fails_closed(tmp_path):
    registry = tmp_path / "factories.json"
    portfolio = tmp_path / "portfolio.json"
    _write(registry, {"factories": []})
    _write(portfolio, {"layers": [{"id": "verticals"}], "maturity_gates": [{"id": "G0"}], "portfolio": [{"id": "phantom", "layer": "verticals", "family": "test", "source_status": "registered", "maturity": "G0"}]})
    with pytest.raises(PortfolioError, match="unverified registered factories"):
        load_portfolio(portfolio, registry)


def test_unregistered_future_factory_is_allowed(tmp_path):
    registry = tmp_path / "factories.json"
    portfolio = tmp_path / "portfolio.json"
    _write(registry, {"factories": []})
    _write(portfolio, {"layers": [{"id": "verticals"}], "maturity_gates": [{"id": "G1"}], "portfolio": [{"id": "future", "layer": "verticals", "family": "recovery-assurance", "source_status": "unregistered", "maturity": "G1"}]})
    assert load_portfolio(portfolio, registry)["portfolio"][0]["id"] == "future"
