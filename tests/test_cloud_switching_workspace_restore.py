from decimal import Decimal
import json

import pytest

from cloud_switching.baseline import BaselineCost, Certainty, CurrentStateBaseline
from cloud_switching.incentives import Incentive, IncentiveStatus
from cloud_switching.service import build_decision_package
from cloud_switching.synthetic import synthetic_companies
from cloud_switching.workspace import DecisionWorkspace, WorkspaceAccessError

D = Decimal


def make_package(tenant_id: str):
    case = synthetic_companies()["alpha_manufacturing_eu"].case
    baseline = CurrentStateBaseline(
        company_id=tenant_id,
        components=[BaselineCost("current", case.current_annual_cost, Certainty.KNOWN, source_id="bill")],
    )
    incentives = [
        Incentive(
            incentive_id="provider",
            program="Provider funding",
            status=IncentiveStatus.PARTIALLY_RECEIVED,
            approved_amount=case.provider_credit_approved,
            received_amount=case.provider_credit_received,
            approval_evidence_id="approval-provider",
            receipt_evidence_id="receipt-provider",
        ),
        Incentive(
            incentive_id="partner",
            program="Partner funding",
            status=IncentiveStatus.PARTIALLY_RECEIVED,
            approved_amount=case.partner_incentive_approved,
            received_amount=case.partner_incentive_received,
            approval_evidence_id="approval-partner",
            receipt_evidence_id="receipt-partner",
        ),
    ]
    return build_decision_package(baseline, case, incentives)


def test_backup_restore_roundtrip_preserves_payload_hash_and_version():
    source = DecisionWorkspace()
    package = make_package("tenant-a")
    saved = source.save(tenant_id="tenant-a", package_id="case-1", package=package)
    backup = source.backup(tenant_id="tenant-a")

    restored = DecisionWorkspace()
    assert restored.restore(tenant_id="tenant-a", backup_json=backup) == 1
    record = restored.require(tenant_id="tenant-a", package_id="case-1")
    assert record.payload == package
    assert record.content_hash == saved.content_hash
    assert record.version == saved.version


def test_restore_rejects_modified_financial_payload():
    source = DecisionWorkspace()
    source.save(tenant_id="tenant-a", package_id="case-1", package=make_package("tenant-a"))
    document = json.loads(source.backup(tenant_id="tenant-a"))
    document["records"][0]["payload"]["captured_incentives"] = "999999999"

    with pytest.raises(ValueError, match="hash mismatch"):
        DecisionWorkspace().restore(tenant_id="tenant-a", backup_json=json.dumps(document))


def test_restore_rejects_wrong_tenant_scope():
    source = DecisionWorkspace()
    source.save(tenant_id="tenant-a", package_id="case-1", package=make_package("tenant-a"))
    backup = source.backup(tenant_id="tenant-a")
    with pytest.raises(WorkspaceAccessError):
        DecisionWorkspace().restore(tenant_id="tenant-b", backup_json=backup)
