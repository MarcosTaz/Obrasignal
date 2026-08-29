from decimal import Decimal as D

import pytest

from cloud_switching.labour import ActivityCode, LabourEntry, productization_gate, summarize_labour


def test_labour_summary_separates_rework_and_revenue_rate():
    summary = summarize_labour(
        [
            LabourEntry(ActivityCode.ESTATE, D("1.0"), "pilot-1"),
            LabourEntry(ActivityCode.BILLING, D("1.5"), "pilot-1"),
            LabourEntry(ActivityCode.OPTIONS, D("2.0"), "pilot-1"),
            LabourEntry(ActivityCode.REWORK, D("0.5"), "pilot-1"),
        ],
        revenue=D("1500"),
    )
    assert summary.total_hours == D("5.0")
    assert summary.rework_hours == D("0.5")
    assert summary.productive_hours == D("4.5")
    assert summary.revenue_per_human_hour == D("300.00")


def test_labour_summary_cannot_mix_customer_cases():
    with pytest.raises(ValueError, match="cannot mix cases"):
        summarize_labour(
            [
                LabourEntry(ActivityCode.INTAKE, D("1"), "a"),
                LabourEntry(ActivityCode.INTAKE, D("1"), "b"),
            ]
        )


def test_productization_gate_measures_more_before_twenty_outcomes():
    assert productization_gate(
        median_lifecycle_hours=D("30"),
        manual_material_field_share=D("0.9"),
        outcomes=19,
    ) == "MEASURE_MORE"


def test_productization_gate_downgrades_linear_service_after_twenty_outcomes():
    assert productization_gate(
        median_lifecycle_hours=D("13"),
        manual_material_field_share=D("0.30"),
        outcomes=20,
    ) == "DOWNGRADE_PRODUCTIZATION"
    assert productization_gate(
        median_lifecycle_hours=D("10"),
        manual_material_field_share=D("0.41"),
        outcomes=25,
    ) == "DOWNGRADE_PRODUCTIZATION"


def test_productization_gate_remains_alive_only_under_both_thresholds():
    assert productization_gate(
        median_lifecycle_hours=D("10"),
        manual_material_field_share=D("0.35"),
        outcomes=30,
    ) == "PRODUCTIZATION_ALIVE"
