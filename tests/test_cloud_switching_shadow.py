from cloud_switching.decision import Decision
from cloud_switching.shadow import run_alpha_shadow_customer


def test_shadow_customer_runs_complete_assurance_loop():
    result = run_alpha_shadow_customer()
    assert result.delivery.decision.decision is Decision.SWITCH
    assert result.delivery.options.economic_winner_id == result.expected_unsubsidized_winner
    assert result.delivery.options.customer_cash_winner_id == result.expected_customer_cash_winner
    assert result.delivery.outcome is not None
    assert result.delivery.outcome.migration_cost_variance > 0
    assert result.delivery.outcome.duration_variance_days > 0
    assert result.delivery.outcome.provider_incentive_variance < 0
    assert result.delivery.outcome.verified_for_benchmark
    assert result.phased_run.migrated_fraction_at_end == 1
    assert result.phased_run.renewal_overlap_cost > 0


def test_shadow_customer_exposes_provider_subsidy_conflict_instead_of_hiding_it():
    result = run_alpha_shadow_customer()
    assert result.expected_unsubsidized_winner != result.expected_customer_cash_winner
