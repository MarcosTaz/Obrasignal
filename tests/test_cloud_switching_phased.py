from decimal import Decimal

import pytest

from cloud_switching.phased import MigrationWave, PhasedMigrationPlan, calculate_phased_run_cost

D = Decimal


def test_full_cutover_without_lag_replaces_source_cost_immediately():
    plan = PhasedMigrationPlan(
        source_annual_run_cost=D("120000"),
        target_annual_run_cost=D("60000"),
        waves=[MigrationWave(1, D("1"))],
    )
    result = calculate_phased_run_cost(plan, 12)
    assert result.source_run_cost == D("0")
    assert result.target_run_cost == D("60000")
    assert result.total_run_cost == D("60000")
    assert result.migrated_fraction_at_end == D("1")


def test_decommission_lag_creates_real_dual_run_cost():
    no_lag = PhasedMigrationPlan(
        source_annual_run_cost=D("120000"),
        target_annual_run_cost=D("60000"),
        waves=[MigrationWave(1, D("1"))],
        decommission_lag_months=0,
    )
    lagged = PhasedMigrationPlan(
        source_annual_run_cost=D("120000"),
        target_annual_run_cost=D("60000"),
        waves=[MigrationWave(1, D("1"))],
        decommission_lag_months=3,
    )
    assert calculate_phased_run_cost(lagged, 12).total_run_cost > calculate_phased_run_cost(no_lag, 12).total_run_cost


def test_renewal_overlap_is_never_hidden_inside_target_run_rate():
    plan = PhasedMigrationPlan(
        source_annual_run_cost=D("120000"),
        target_annual_run_cost=D("60000"),
        waves=[MigrationWave(1, D("1"))],
        renewal_overlap_months=4,
        renewal_overlap_monthly_cost=D("2500"),
    )
    result = calculate_phased_run_cost(plan, 12)
    assert result.renewal_overlap_cost == D("10000")
    assert result.total_run_cost == D("70000")


def test_partial_exit_preserves_unmigrated_source_fraction():
    plan = PhasedMigrationPlan(
        source_annual_run_cost=D("120000"),
        target_annual_run_cost=D("60000"),
        waves=[MigrationWave(1, D("0.5"))],
    )
    result = calculate_phased_run_cost(plan, 12)
    assert result.source_run_cost == D("60000.0")
    assert result.target_run_cost == D("30000.0")
    assert result.total_run_cost == D("90000.0")
    assert result.migrated_fraction_at_end == D("0.5")


def test_cumulative_wave_fraction_above_one_fails_closed():
    plan = PhasedMigrationPlan(
        source_annual_run_cost=D("120000"),
        target_annual_run_cost=D("60000"),
        waves=[MigrationWave(1, D("0.7")), MigrationWave(2, D("0.4"))],
    )
    with pytest.raises(ValueError):
        calculate_phased_run_cost(plan, 12)
