from decimal import Decimal

import pytest

from cloud_switching.baseline import BaselineCost, Certainty, CurrentStateBaseline, MissingMaterialInput

D = Decimal


def test_material_unknown_prevents_false_baseline_total():
    baseline = CurrentStateBaseline(
        company_id="alpha",
        components=[
            BaselineCost("license", D("80000"), Certainty.KNOWN, source_id="contract-1"),
            BaselineCost("support", None, Certainty.UNKNOWN),
        ],
    )
    assert baseline.unresolved_material_inputs() == ("support",)
    with pytest.raises(MissingMaterialInput):
        baseline.annual_cost()


def test_non_material_unknown_does_not_silently_change_known_cost_total():
    baseline = CurrentStateBaseline(
        company_id="alpha",
        components=[
            BaselineCost("license", D("80000"), Certainty.KNOWN, source_id="contract-1"),
            BaselineCost("optional_observability", None, Certainty.UNKNOWN, material=False),
        ],
    )
    assert baseline.annual_cost() == D("80000")


def test_known_value_requires_source_evidence():
    baseline = CurrentStateBaseline(
        company_id="alpha",
        components=[BaselineCost("license", D("80000"), Certainty.KNOWN)],
    )
    with pytest.raises(ValueError):
        baseline.validate()


def test_unknown_cannot_be_disguised_as_zero():
    cost = BaselineCost("support", D("0"), Certainty.UNKNOWN)
    with pytest.raises(ValueError):
        cost.validate()


def test_duplicate_component_fails_closed():
    baseline = CurrentStateBaseline(
        company_id="alpha",
        components=[
            BaselineCost("license", D("80000"), Certainty.KNOWN, source_id="contract-1"),
            BaselineCost("license", D("90000"), Certainty.ESTIMATED),
        ],
    )
    with pytest.raises(ValueError):
        baseline.validate()
