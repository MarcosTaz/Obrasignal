from decimal import Decimal

import pytest

from cloud_switching.options import OptionType, SwitchingOption, compare_options

D = Decimal


def test_gross_economic_winner_is_not_changed_by_provider_subsidy():
    retain = SwitchingOption("retain", OptionType.RETAIN, "vmware", "EUR", D("300000"))
    aws = SwitchingOption("aws", OptionType.SWITCH, "aws", "EUR", D("230000"), D("120000"), D("180000"))
    azure = SwitchingOption("azure", OptionType.SWITCH, "azure", "EUR", D("210000"), D("90000"), D("20000"))
    result = compare_options([retain, aws, azure], horizon_years=3)
    assert result.economic_winner_id == "azure"
    assert result.customer_cash_winner_id == "aws"


def test_retain_can_correctly_win_against_bad_migrations():
    retain = SwitchingOption("retain", OptionType.RETAIN, "vmware", "EUR", D("220000"))
    aws = SwitchingOption("aws", OptionType.SWITCH, "aws", "EUR", D("230000"), D("120000"), D("50000"))
    gcp = SwitchingOption("gcp", OptionType.SWITCH, "gcp", "EUR", D("240000"), D("100000"), D("90000"))
    result = compare_options([retain, aws, gcp], horizon_years=3)
    assert result.economic_winner_id == "retain"


def test_cross_currency_comparison_fails_closed_without_fx_normalization():
    eur = SwitchingOption("eur", OptionType.RETAIN, "vmware", "EUR", D("100"))
    usd = SwitchingOption("usd", OptionType.SWITCH, "aws", "USD", D("90"), D("10"))
    with pytest.raises(ValueError, match="normalized currency"):
        compare_options([eur, usd])


def test_duplicate_option_id_fails_closed():
    a = SwitchingOption("same", OptionType.RETAIN, "vmware", "EUR", D("100"))
    b = SwitchingOption("same", OptionType.SWITCH, "aws", "EUR", D("90"), D("10"))
    with pytest.raises(ValueError, match="duplicate option id"):
        compare_options([a, b])


def test_retain_option_cannot_be_made_artificially_cheaper_with_migration_credit():
    bad = SwitchingOption("retain", OptionType.RETAIN, "vmware", "EUR", D("100"), received_incentives=D("10"))
    switch = SwitchingOption("switch", OptionType.SWITCH, "aws", "EUR", D("90"), D("10"))
    with pytest.raises(ValueError, match="migration incentives"):
        compare_options([bad, switch])
