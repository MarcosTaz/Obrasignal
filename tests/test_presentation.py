from datetime import datetime, timezone
from bangs.costs import CostBasis, CostLine, assess_cost_lines
from bangs.money import Money
from bangs.presentation import build_executive_result
from bangs.true_cost import JobCostCategory, JobCostContribution, assess_true_job_cost


def test_executive_result_says_total_unknown_when_material_category_unknown():
    known = assess_cost_lines((CostLine("known", Money.of(320000, "EUR"), CostBasis.FACT),))
    unknown = assess_cost_lines((), unknown_components=("labour", "insurance"))
    total = assess_true_job_cost((
        JobCostContribution(JobCostCategory.DIRECT_KNOWN_COST, known),
        JobCostContribution(JobCostCategory.OTHER, unknown),
    ))
    result = build_executive_result(total)
    assert result.known_cost == {"amount": "320000", "currency": "EUR"}
    assert result.total_job_cost_state == "TOTAL_JOB_COST_UNKNOWN"
    assert any("labour" in x for x in result.unknowns)


def test_executive_result_does_not_rank_cost_drivers_across_currencies():
    eur = assess_cost_lines((CostLine("eur", Money.of(100, "EUR"), CostBasis.FACT),))
    pln = assess_cost_lines((CostLine("pln", Money.of(50, "PLN"), CostBasis.FACT),))
    total = assess_true_job_cost((
        JobCostContribution(JobCostCategory.MATERIAL_LANDED_COST, eur),
        JobCostContribution(JobCostCategory.EQUIPMENT_COST, pln),
    ))
    result = build_executive_result(total)
    assert result.major_cost_drivers == ()
    assert "MULTI_CURRENCY_UNRESOLVED" in result.major_risks
