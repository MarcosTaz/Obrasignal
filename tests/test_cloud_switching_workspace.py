from decimal import Decimal

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


def test_save_and_return_preserves_decision_package_and_hash():
    workspace = DecisionWorkspace()
    package = make_package("tenant-a")
    saved = workspace.save(tenant_id="tenant-a", package_id="case-1", package=package)
    loaded = workspace.require(tenant_id="tenant-a", package_id="case-1")
    assert loaded.payload == package
    assert loaded.content_hash == saved.content_hash
    assert loaded.version == 1


def test_second_save_versions_same_tenant_package():
    workspace = DecisionWorkspace()
    package = make_package("tenant-a")
    workspace.save(tenant_id="tenant-a", package_id="case-1", package=package)
    second = workspace.save(tenant_id="tenant-a", package_id="case-1", package=package)
    assert second.version == 2


def test_cross_tenant_lookup_returns_no_record():
    workspace = DecisionWorkspace()
    workspace.save(tenant_id="tenant-a", package_id="case-1", package=make_package("tenant-a"))
    assert workspace.load(tenant_id="tenant-b", package_id="case-1") is None
    with pytest.raises(KeyError):
        workspace.require(tenant_id="tenant-b", package_id="case-1")


def test_tenant_cannot_save_another_company_package():
    workspace = DecisionWorkspace()
    with pytest.raises(WorkspaceAccessError):
        workspace.save(tenant_id="tenant-b", package_id="case-1", package=make_package("tenant-a"))


def test_backup_contains_only_requested_tenant():
    workspace = DecisionWorkspace()
    workspace.save(tenant_id="tenant-a", package_id="a", package=make_package("tenant-a"))
    workspace.save(tenant_id="tenant-b", package_id="b", package=make_package("tenant-b"))
    backup = workspace.backup(tenant_id="tenant-a")
    assert '"tenant_id": "tenant-a"' in backup
    assert '"tenant_id": "tenant-b"' not in backup
