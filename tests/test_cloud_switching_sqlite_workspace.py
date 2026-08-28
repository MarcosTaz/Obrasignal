from cloud_switching.baseline import BaselineCost, Certainty, CurrentStateBaseline
from cloud_switching.incentives import Incentive, IncentiveStatus
from cloud_switching.service import build_decision_package
from cloud_switching.sqlite_workspace import SQLiteDecisionWorkspace
from cloud_switching.synthetic import synthetic_companies


def make_package(tenant_id: str):
    case = synthetic_companies()["alpha_manufacturing_eu"].case
    baseline = CurrentStateBaseline(
        company_id=tenant_id,
        components=[BaselineCost("current", case.current_annual_cost, Certainty.KNOWN, source_id="billing")],
    )
    incentives = [
        Incentive(
            incentive_id="provider",
            program="Provider funding",
            status=IncentiveStatus.PARTIALLY_RECEIVED,
            approved_amount=case.provider_credit_approved,
            received_amount=case.provider_credit_received,
            approval_evidence_id="provider-approval",
            receipt_evidence_id="provider-receipt",
        ),
        Incentive(
            incentive_id="partner",
            program="Partner funding",
            status=IncentiveStatus.PARTIALLY_RECEIVED,
            approved_amount=case.partner_incentive_approved,
            received_amount=case.partner_incentive_received,
            approval_evidence_id="partner-approval",
            receipt_evidence_id="partner-receipt",
        ),
    ]
    return build_decision_package(baseline, case, incentives)


def test_sqlite_workspace_survives_process_style_reopen(tmp_path):
    path = tmp_path / "cloud-switching.db"
    first = SQLiteDecisionWorkspace(path)
    package = make_package("tenant-a")
    saved = first.save(tenant_id="tenant-a", package_id="case-1", package=package)

    reopened = SQLiteDecisionWorkspace(path)
    loaded = reopened.require(tenant_id="tenant-a", package_id="case-1")
    assert loaded.payload == package
    assert loaded.content_hash == saved.content_hash
    assert loaded.version == 1


def test_sqlite_workspace_scopes_lookup_by_tenant(tmp_path):
    workspace = SQLiteDecisionWorkspace(tmp_path / "cloud-switching.db")
    workspace.save(tenant_id="tenant-a", package_id="case-1", package=make_package("tenant-a"))
    assert workspace.load(tenant_id="tenant-b", package_id="case-1") is None


def test_sqlite_workspace_versions_updates(tmp_path):
    workspace = SQLiteDecisionWorkspace(tmp_path / "cloud-switching.db")
    package = make_package("tenant-a")
    workspace.save(tenant_id="tenant-a", package_id="case-1", package=package)
    second = workspace.save(tenant_id="tenant-a", package_id="case-1", package=package)
    assert second.version == 2
