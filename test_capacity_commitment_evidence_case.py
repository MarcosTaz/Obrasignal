from factories.capacity_commitment.evidence import (
    ExtractedFact,
    FactType,
    ReviewState,
)
from factories.capacity_commitment.evidence_case import build_case_draft


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


def complete_facts():
    return [
        confirmed("customer", FactType.CUSTOMER_ID, "oem-1"),
        confirmed("program", FactType.PROGRAM_ID, "program-1"),
        confirmed("contract", FactType.CONTRACT_ID, "lta-1"),
        confirmed("currency", FactType.CURRENCY, "EUR"),
        confirmed("unit", FactType.UNIT, "parts"),
        confirmed("state", FactType.COMMITMENT_STATE, "FIRM"),
        confirmed("committed", FactType.COMMITTED_UNITS, "100000"),
        confirmed("cost", FactType.DEDICATED_COST, "1200000"),
        confirmed("basis", FactType.AMORTIZATION_BASIS_UNITS, "100000"),
        confirmed("actual-1", FactType.ACTUAL_UNITS, "40000", scope_ref="shipment-a"),
        confirmed("actual-2", FactType.ACTUAL_UNITS, "30000", scope_ref="shipment-b"),
    ]


def test_complete_confirmed_evidence_becomes_draft_not_entitlement():
    draft = build_case_draft("supplier-1", complete_facts())
    assert draft.ready_for_human_case_creation is True
    assert draft.missing_required == ()
    assert draft.conflicts == ()
    assert draft.case_inputs["ACTUAL_UNITS"] == "70000"
    assert draft.case_inputs["COMMITTED_UNITS"] == "100000"
    assert "evidence_supported" in draft.human_control_gates
    assert "duplicate_claim_reviewed" in draft.human_control_gates
    assert "recoverable_amount" not in draft.case_inputs
    assert "claimable_amount" not in draft.case_inputs


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


def test_missing_contract_and_unit_are_explicit_not_inferred():
    facts = [item for item in complete_facts() if item.fact_type not in {FactType.CONTRACT_ID, FactType.UNIT}]
    draft = build_case_draft("supplier-1", facts)
    assert draft.ready_for_human_case_creation is False
    assert draft.missing_required == ("CONTRACT_ID", "UNIT")
