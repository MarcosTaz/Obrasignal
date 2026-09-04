from decimal import Decimal

import pytest

from factories.capacity_commitment.revision_delta import compare_revisions
from factories.capacity_commitment.state import AssistedCaseState
from factories.capacity_commitment.synthetic_cases import case


def state(case_id, *, actual="80000", evidence=("contract:1",), missing=(), deadline="2099-12-31", **case_overrides):
    return AssistedCaseState(
        tenant_id="tenant-a",
        company_id="supplier-1",
        customer_id="oem-1",
        program_id="program-1",
        period_id="2026Q2",
        unit="parts",
        recovery_case=case(case_id, actual_units=Decimal(actual), **case_overrides),
        evidence_refs=evidence,
        missing_evidence=missing,
        deadline=deadline,
        contract_id="lta-1",
    )


def changes_by_field(items):
    return {item.field: (item.before, item.after) for item in items}


def test_revision_delta_explains_source_and_finding_change():
    parent = state("case-v1", actual="80000", evidence=("contract:1",), missing=("actuals:final",))
    child = state(
        "case-v2",
        actual="70000",
        evidence=("contract:1", "actuals:final"),
        missing=(),
        prior_payment=Decimal("10000"),
    )
    delta = compare_revisions(parent, child)
    source = changes_by_field(delta.source_changes)
    result = changes_by_field(delta.result_changes)

    assert delta.parent_case_id == "case-v1"
    assert delta.child_case_id == "case-v2"
    assert source["actual_units"] == ("80000", "70000")
    assert source["prior_payment"] == ("0", "10000")
    assert delta.evidence_added == ("actuals:final",)
    assert delta.missing_evidence_resolved == ("actuals:final",)
    assert result["shortfall_units"] == ("20000", "30000")
    assert result["claimable_amount"] == ("100000", "140000")
    assert delta.finding_changed is True


def test_revision_delta_can_show_evidence_change_without_fake_result_change():
    parent = state("case-v1", evidence=("contract:1",), missing=("supporting-email",))
    child = state("case-v2", evidence=("contract:1", "email:2"), missing=())
    delta = compare_revisions(parent, child)
    assert delta.evidence_added == ("email:2",)
    assert delta.missing_evidence_resolved == ("supporting-email",)
    assert delta.result_changes == ()
    assert delta.reasons_added == ()
    assert delta.reasons_removed == ()
    assert delta.finding_changed is False


def test_revision_delta_recomputes_unknown_to_recoverable_from_source_state():
    parent = state("case-v1", explicit_recovery_right=None)
    child = state("case-v2", explicit_recovery_right=True)
    delta = compare_revisions(parent, child)
    result = changes_by_field(delta.result_changes)
    assert result["recoverability_state"] == ("UNKNOWN", "RECOVERABLE")
    assert result["claimable_amount"] == ("0", "100000")
    assert "recovery_right_unknown" in delta.reasons_removed
    assert "commitment_right_evidence_integrity_and_notice_supported" in delta.reasons_added


def test_revision_delta_rejects_changed_period_unit_or_tenant():
    parent = state("case-v1")
    changed_period = AssistedCaseState(**{**parent.__dict__, "recovery_case": case("case-v2"), "period_id": "2026Q3"})
    changed_unit = AssistedCaseState(**{**parent.__dict__, "recovery_case": case("case-v2"), "unit": "kg"})
    foreign = AssistedCaseState(**{**parent.__dict__, "tenant_id": "tenant-b", "recovery_case": case("case-v2")})

    with pytest.raises(ValueError, match="period_id"):
        compare_revisions(parent, changed_period)
    with pytest.raises(ValueError, match="unit"):
        compare_revisions(parent, changed_unit)
    with pytest.raises(PermissionError, match="tenant"):
        compare_revisions(parent, foreign)


def test_revision_delta_requires_distinct_immutable_snapshots():
    item = state("same")
    with pytest.raises(ValueError, match="distinct case_ids"):
        compare_revisions(item, item)
