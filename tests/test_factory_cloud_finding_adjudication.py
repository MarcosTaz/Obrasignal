import pytest

from factory_cloud.finding_adjudication import FindingAdjudicationError, FindingAdjudicationLedger


def test_shadow_adjudication_defaults_fail_closed_and_requires_evidence(tmp_path):
    ledger = FindingAdjudicationLedger(tmp_path / "assurance.sqlite3")
    decision = ledger.register_shadow(
        tenant_id="tenant-a", finding_id="finding-1", vertical="contractcredit", requires_breach=True,
    )
    assert decision.entitlement_state == "UNKNOWN"
    assert decision.breach_state == "NOT_ESTABLISHED"
    assert decision.actionable is False
    with pytest.raises(FindingAdjudicationError, match="not actionably adjudicated"):
        ledger.require_actionable(tenant_id="tenant-a", finding_id="finding-1")
    with pytest.raises(FindingAdjudicationError, match="decision evidence"):
        ledger.adjudicate(
            tenant_id="tenant-a", finding_id="finding-1", adjudicator="reviewer",
            entitlement_established=True, breach_established=True,
            evidence_ref="", reason="supported",
        )


def test_contractcredit_requires_both_entitlement_and_breach(tmp_path):
    ledger = FindingAdjudicationLedger(tmp_path / "assurance.sqlite3")
    ledger.register_shadow(
        tenant_id="tenant-a", finding_id="finding-1", vertical="contractcredit", requires_breach=True,
    )
    partial = ledger.adjudicate(
        tenant_id="tenant-a", finding_id="finding-1", adjudicator="reviewer",
        entitlement_established=True, breach_established=False,
        evidence_ref="decision-packet", reason="entitlement clause found but breach not established",
    )
    assert partial.entitlement_state == "ESTABLISHED"
    assert partial.breach_state == "NOT_ESTABLISHED"
    assert partial.actionable is False
    complete = ledger.adjudicate(
        tenant_id="tenant-a", finding_id="finding-1", adjudicator="reviewer",
        entitlement_established=True, breach_established=True,
        evidence_ref="decision-packet-2", reason="contract and account evidence establish both dimensions",
    )
    assert complete.actionable is True


def test_aviation_rejects_breach_dimension_and_requires_entitlement(tmp_path):
    ledger = FindingAdjudicationLedger(tmp_path / "assurance.sqlite3")
    ledger.register_shadow(
        tenant_id="airline", finding_id="finding-1",
        vertical="aviation-lease-entitlement-recovery", requires_breach=False,
    )
    with pytest.raises(FindingAdjudicationError, match="not applicable"):
        ledger.adjudicate(
            tenant_id="airline", finding_id="finding-1", adjudicator="reviewer",
            entitlement_established=True, breach_established=True,
            evidence_ref="lease-clause", reason="not a breach-based vertical",
        )
    decision = ledger.adjudicate(
        tenant_id="airline", finding_id="finding-1", adjudicator="reviewer",
        entitlement_established=True, breach_established=None,
        evidence_ref="lease-clause-and-event", reason="specific lease/event evidence establishes entitlement",
    )
    assert decision.breach_state == "NOT_APPLICABLE"
    assert decision.actionable is True


def test_adjudication_is_tenant_scoped_and_hashes_raw_decision_material(tmp_path):
    path = tmp_path / "assurance.sqlite3"
    ledger = FindingAdjudicationLedger(path)
    ledger.register_shadow(
        tenant_id="tenant-a", finding_id="same-id", vertical="contractcredit", requires_breach=True,
    )
    ledger.register_shadow(
        tenant_id="tenant-b", finding_id="same-id", vertical="contractcredit", requires_breach=True,
    )
    raw_evidence = "customer-contract-clause-sensitive-ref"
    raw_reason = "sensitive adjudicator reasoning wording"
    ledger.adjudicate(
        tenant_id="tenant-a", finding_id="same-id", adjudicator="reviewer-a",
        entitlement_established=True, breach_established=True,
        evidence_ref=raw_evidence, reason=raw_reason,
    )
    assert ledger.require_actionable(tenant_id="tenant-a", finding_id="same-id").actionable is True
    with pytest.raises(FindingAdjudicationError, match="not actionably adjudicated"):
        ledger.require_actionable(tenant_id="tenant-b", finding_id="same-id")
    persisted = path.read_bytes()
    assert raw_evidence.encode() not in persisted
    assert raw_reason.encode() not in persisted
