from factories.capacity_commitment.engine import (
    CostRecoveryMode,
    ExposureType,
    RecoverabilityState,
    evaluate_recoverability,
)
from factories.capacity_commitment.evidence import (
    ExtractedFact,
    FactType,
    ReviewState,
)
from factories.capacity_commitment.evidence_case import (
    HumanCaseControls,
    build_case_draft,
    build_state_from_confirmed_evidence,
)


def confirmed(fact_id, fact_type, value, *, scope_ref=None, evidence_id="e1"):
    return ExtractedFact(
        tenant_id="tenant-a",
        fact_id=fact_id,
        evidence_id=evidence_id,
        fact_type=fact_type,
        raw_value=value,
        normalized_value=value,
        scope_ref=scope_ref,
        page_ref="p.1",
        clause_ref="1.1",
        review_state=ReviewState.CONFIRMED,
    )


def complete_facts(*, include_entitlement=True):
    items = [
        confirmed("customer", FactType.CUSTOMER_ID, "oem-1"),
        confirmed("program", FactType.PROGRAM_ID, "program-1"),
        confirmed("contract", FactType.CONTRACT_ID, "lta-1"),
        confirmed("period", FactType.PERIOD_ID, "2026Q2"),
        confirmed("currency", FactType.CURRENCY, "EUR"),
        confirmed("unit", FactType.UNIT, "parts"),
        confirmed("state", FactType.COMMITMENT_STATE, "FIRM"),
        confirmed("committed", FactType.COMMITTED_UNITS, "100000"),
        confirmed("cost", FactType.DEDICATED_COST, "1200000"),
        confirmed("basis", FactType.AMORTIZATION_BASIS_UNITS, "100000"),
        confirmed("mitigation", FactType.MITIGATION, "0"),
        confirmed("prior", FactType.PRIOR_PAYMENT, "0"),
        confirmed("actual-1", FactType.ACTUAL_UNITS, "40000", scope_ref="shipment-a"),
        confirmed("actual-2", FactType.ACTUAL_UNITS, "30000", scope_ref="shipment-b"),
    ]
    if include_entitlement:
        items.extend(
            [
                confirmed("right", FactType.EXPLICIT_RECOVERY_RIGHT, "true"),
                confirmed("notice", FactType.NOTICE_VALID, "true"),
                confirmed("deadline", FactType.DEADLINE, "2026-12-31"),
            ]
        )
    return items


def controls(**overrides):
    values = dict(
        evidence_supported=True,
        asset_dedicated=True,
        already_fully_amortized=False,
        already_paid=False,
        exposure_type=ExposureType.DEDICATED_CAPEX,
        cost_recovery_mode=CostRecoveryMode.UNIT_AMORTIZED,
        duplicate_claim=False,
        customer_matches=True,
        program_matches=True,
        period_matches=True,
        currency_matches=True,
        unit_matches=True,
        actuals_complete=True,
        actuals_deduplicated=True,
        cancelled_orders_excluded=True,
        amortization_verified=True,
        asset_dedication_verified=True,
        mitigation_reviewed=True,
        prior_recovery_reviewed=True,
        notice_window_verified=True,
        contract_matches=True,
        contract_current=True,
        amendment_reviewed=True,
        amendment_matches=True,
        duplicate_claim_reviewed=True,
    )
    values.update(overrides)
    return HumanCaseControls(**values)


def test_complete_confirmed_evidence_becomes_draft_not_entitlement():
    draft = build_case_draft("supplier-1", complete_facts())
    assert draft.ready_for_human_case_creation is True
    assert draft.missing_required == ()
    assert draft.conflicts == ()
    assert draft.case_inputs["ACTUAL_UNITS"] == "70000"
    assert draft.case_inputs["COMMITTED_UNITS"] == "100000"
    assert draft.case_inputs["MITIGATION"] == "0"
    assert draft.case_inputs["PRIOR_PAYMENT"] == "0"
    assert draft.case_inputs["PERIOD_ID"] == "2026Q2"
    assert "evidence_supported" in draft.human_control_gates
    assert "duplicate_claim_reviewed" in draft.human_control_gates
    assert "recoverable_amount" not in draft.case_inputs
    assert "claimable_amount" not in draft.case_inputs


def test_confirmed_evidence_plus_explicit_review_can_create_positive_case():
    state = build_state_from_confirmed_evidence(
        tenant_id="tenant-a",
        company_id="supplier-1",
        case_id="case-1",
        facts=complete_facts(),
        controls=controls(),
    )
    result = evaluate_recoverability(state.recovery_case)
    assert state.period_id == "2026Q2"
    assert state.unit == "parts"
    assert state.recovery_case.actual_units == 70000
    assert result.recoverability_state is RecoverabilityState.RECOVERABLE
    assert result.claimable_amount == 360000


def test_missing_entitlement_source_cannot_be_invented_by_human_controls():
    state = build_state_from_confirmed_evidence(
        tenant_id="tenant-a",
        company_id="supplier-1",
        case_id="case-no-right",
        facts=complete_facts(include_entitlement=False),
        controls=controls(notice_window_verified=False),
    )
    assert state.recovery_case.explicit_recovery_right is None
    assert state.recovery_case.notice_valid is None
    assert "source_fact:EXPLICIT_RECOVERY_RIGHT" in state.missing_evidence
    result = evaluate_recoverability(state.recovery_case)
    assert result.recoverability_state is RecoverabilityState.UNKNOWN
    assert result.claimable_amount == 0


def test_unreviewed_required_fact_stays_missing():
    facts = complete_facts()
    facts[0] = ExtractedFact(
        tenant_id="tenant-a",
        fact_id="customer",
        evidence_id="e1",
        fact_type=FactType.CUSTOMER_ID,
        raw_value="oem-1",
        normalized_value="oem-1",
        page_ref="p.1",
        clause_ref="1.1",
        review_state=ReviewState.UNREVIEWED,
    )
    draft = build_case_draft("supplier-1", facts)
    assert draft.ready_for_human_case_creation is False
    assert "CUSTOMER_ID" in draft.missing_required


def test_conflicting_confirmed_fact_blocks_case_draft_readiness():
    facts = complete_facts()
    facts.append(confirmed("committed-2", FactType.COMMITTED_UNITS, "90000", evidence_id="e2"))
    draft = build_case_draft("supplier-1", facts)
    assert draft.ready_for_human_case_creation is False
    assert "conflicting confirmed COMMITTED_UNITS" in draft.conflicts


def test_duplicate_actual_scope_blocks_case_draft_even_when_other_inputs_exist():
    facts = complete_facts()
    facts.append(confirmed("actual-dup", FactType.ACTUAL_UNITS, "100", scope_ref="shipment-a"))
    draft = build_case_draft("supplier-1", facts)
    assert draft.ready_for_human_case_creation is False
    assert "ACTUAL_UNITS" in draft.missing_required
    assert "duplicate confirmed ACTUAL_UNITS scope shipment-a" in draft.conflicts


def test_missing_contract_and_nomination_anchor_and_unit_are_explicit_not_inferred():
    facts = [
        item
        for item in complete_facts()
        if item.fact_type not in {FactType.CONTRACT_ID, FactType.NOMINATION_ID, FactType.UNIT}
    ]
    draft = build_case_draft("supplier-1", facts)
    assert draft.ready_for_human_case_creation is False
    assert draft.missing_required == ("CONTRACT_ID_OR_NOMINATION_ID", "UNIT")


def test_absent_mitigation_or_prior_payment_never_silently_defaults_to_zero():
    facts = [
        item
        for item in complete_facts()
        if item.fact_type not in {FactType.MITIGATION, FactType.PRIOR_PAYMENT}
    ]
    draft = build_case_draft("supplier-1", facts)
    assert draft.ready_for_human_case_creation is False
    assert "MITIGATION" in draft.missing_required
    assert "PRIOR_PAYMENT" in draft.missing_required
