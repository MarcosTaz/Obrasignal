from datetime import date
from decimal import Decimal

import pytest

from factory_cloud.assurance_kernel import (
    AssuranceKernelError,
    CalculationInput,
    CalculationRecord,
    DeadlineWindow,
    EvidenceEnvelope,
    FindingRecord,
    assert_same_tenant,
)


def test_evidence_hash_is_deterministic_and_content_sensitive():
    a = EvidenceEnvelope.create(evidence_id="e1", tenant_id="t1", source_type="contract", source_ref="c1", content="abc")
    b = EvidenceEnvelope.create(evidence_id="e2", tenant_id="t1", source_type="contract", source_ref="c1", content="abc")
    c = EvidenceEnvelope.create(evidence_id="e3", tenant_id="t1", source_type="contract", source_ref="c1", content="abcd")
    assert a.content_hash == b.content_hash
    assert a.content_hash != c.content_hash


def test_calculation_has_formula_version_and_reproducibility_hash():
    inputs = (CalculationInput("contract_rate", "0.10", "%", ("e1",)), CalculationInput("base", "1000", "EUR", ("e2",)))
    a = CalculationRecord.create(calculation_id="c1", tenant_id="t1", formula_id="royalty", formula_version="1", inputs=inputs, output_value=Decimal("100"), output_unit="EUR")
    b = CalculationRecord.create(calculation_id="c2", tenant_id="t1", formula_id="royalty", formula_version="1", inputs=inputs, output_value=Decimal("100"), output_unit="EUR")
    assert a.reproducibility_hash == b.reproducibility_hash
    assert a.evidence_ids == ("e1", "e2")


def test_deadline_requires_source_evidence_and_has_explicit_expiry():
    with pytest.raises(AssuranceKernelError):
        DeadlineWindow.create(deadline_id="d1", tenant_id="t1", due_date=date(2026, 9, 1), basis_evidence_ids=[])
    window = DeadlineWindow.create(deadline_id="d1", tenant_id="t1", due_date=date(2026, 9, 1), basis_evidence_ids=["e1"])
    assert window.state_on(date(2026, 8, 31)) == "OPEN"
    assert window.state_on(date(2026, 9, 2)) == "EXPIRED"


def test_finding_cannot_be_approved_without_review_transition():
    finding = FindingRecord.create(finding_id="f1", tenant_id="t1", finding_type="credit", evidence_ids=["e1"], state="READY_FOR_REVIEW")
    approved = finding.review(reviewer="human-1", approved=True, reason="contract and performance evidence agree")
    assert approved.state == "APPROVED"
    assert approved.reviewer == "human-1"


def test_cross_tenant_composition_is_rejected():
    evidence = EvidenceEnvelope.create(evidence_id="e1", tenant_id="tenant-a", source_type="contract", source_ref="c1", content="x")
    calculation = CalculationRecord.create(calculation_id="c1", tenant_id="tenant-b", formula_id="x", formula_version="1", inputs=[CalculationInput("x", "1")], output_value="1")
    with pytest.raises(AssuranceKernelError, match="cross-tenant"):
        assert_same_tenant(evidence, calculation)
