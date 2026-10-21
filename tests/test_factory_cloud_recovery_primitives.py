import pytest

from factory_cloud.recovery_primitives import (
    EntitlementBasis,
    FeeLineage,
    RecoveryFingerprint,
    RecoveryPrimitiveError,
    duplicate_fingerprints,
)


def test_entitlement_basis_fails_closed_without_source_evidence():
    with pytest.raises(RecoveryPrimitiveError, match="source evidence"):
        EntitlementBasis.create(entitlement_id="e1", tenant_id="t", domain="aviation", source_evidence_ids=(), rule_ref="clause-1", confidence="SUPPORTED")
    supported = EntitlementBasis.create(entitlement_id="e1", tenant_id="t", domain="aviation", source_evidence_ids=("contract-1",), rule_ref="clause-1", confidence="SUPPORTED")
    unresolved = EntitlementBasis.create(entitlement_id="e2", tenant_id="t", domain="contractcredit", source_evidence_ids=("msa-1",), rule_ref="sla-1", confidence="UNRESOLVED")
    assert supported.actionable is True
    assert unresolved.actionable is False


def test_duplicate_detection_is_tenant_scoped():
    one = RecoveryFingerprint.create(tenant_id="a", vertical="contractcredit", contract_ref="msa", event_ref="inc", remedy_type="credit")
    duplicate = RecoveryFingerprint.create(tenant_id="a", vertical="contractcredit", contract_ref="msa", event_ref="inc", remedy_type="credit")
    other_tenant = RecoveryFingerprint.create(tenant_id="b", vertical="contractcredit", contract_ref="msa", event_ref="inc", remedy_type="credit")
    assert duplicate_fingerprints((one, duplicate, other_tenant)) == (one.fingerprint,)


def test_fee_lineage_is_reproducible_for_both_vertical_economics():
    aviation = FeeLineage.create(fee_id="fa", tenant_id="airline", outcome_id="oa", recovered_amount="75000", fee_rate="0.20", currency="EUR")
    credit = FeeLineage.create(fee_id="fc", tenant_id="enterprise", outcome_id="oc", recovered_amount="5000", fee_rate="0.20", currency="EUR")
    assert aviation.fee_amount == "15000.00"
    assert credit.fee_amount == "1000.00"
    assert aviation.lineage_hash != credit.lineage_hash


def test_fee_lineage_rejects_rate_over_100_percent():
    with pytest.raises(RecoveryPrimitiveError):
        FeeLineage.create(fee_id="f", tenant_id="t", outcome_id="o", recovered_amount="1", fee_rate="1.01", currency="EUR")
