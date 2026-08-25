from pathlib import Path

from bangs.financial import FinancialExposureState, assess_financial_exposure
from capability_registry import capability, enabled_capabilities


ROOT = Path(__file__).resolve().parents[2]


def test_economics_capabilities_remain_research_gated():
    bid = capability("BID_ECONOMICS")
    bangs = capability("BANGS")
    assert bid.state == "RESEARCH"
    assert bangs.state == "RESEARCH"
    assert bid.kill_switch_required is True
    assert bangs.kill_switch_required is True
    assert "BID_ECONOMICS" not in enabled_capabilities()
    assert "BANGS" not in enabled_capabilities()


def test_bangs_does_not_fabricate_financial_exposure_without_provider():
    result = assess_financial_exposure("opp-1", "tenant-a", provider=None)
    assert result.state is FinancialExposureState.PROVIDER_UNAVAILABLE
    assert result.working_capital is None
    assert result.bond_exposure is None
    assert result.retention is None
    assert result.advance is None
    assert result.financial_cost is None


def test_bangs_keeps_bid_economics_and_mobilize_as_external_public_boundaries():
    financial = (ROOT / "bangs" / "financial.py").read_text(encoding="utf-8")
    mobilization = (ROOT / "bangs" / "mobilization.py").read_text(encoding="utf-8")
    assert "import bid_economics" not in financial
    assert "from bid_economics" not in financial
    assert "import mobilize" not in mobilization
    assert "from mobilize" not in mobilization


def test_decimal_money_engines_do_not_import_binary_float_mobilize_contract():
    bid = (ROOT / "bid_economics.py").read_text(encoding="utf-8")
    bangs_money = (ROOT / "bangs" / "money.py").read_text(encoding="utf-8")
    assert "from decimal import" in bid
    assert "from decimal import" in bangs_money
    assert "import mobilize" not in bid
    assert "import mobilize" not in bangs_money
