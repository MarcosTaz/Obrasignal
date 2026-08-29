import pytest

from factory_cloud.shared_contracts import (
    EntitlementSnapshot,
    IdentityPrincipal,
    ReleaseEvidence,
    SharedContractError,
)


def test_identity_contract_is_tenant_scoped_and_role_checked():
    principal = IdentityPrincipal.create(
        tenant_id="tenant-a", subject="user-1", roles=("analyst", "reviewer"), issuer="issuer", audience="app"
    )
    principal.require("analyst")
    with pytest.raises(SharedContractError):
        principal.require("admin")


def test_entitlement_contract_denies_inactive_and_missing_features():
    active = EntitlementSnapshot.create(
        tenant_id="tenant-a", plan_id="pilot", status="ACTIVE", features=("assurance",), provider_ref="sub-1"
    )
    assert active.allows("assurance") is True
    assert active.allows("admin") is False
    suspended = EntitlementSnapshot.create(
        tenant_id="tenant-a", plan_id="pilot", status="SUSPENDED", features=("assurance",)
    )
    assert suspended.allows("assurance") is False


def test_release_contract_requires_exact_sha_and_all_checks():
    revision = "a" * 40
    release = ReleaseEvidence.create(
        revision=revision, required_checks=("python", "mobile"), successful_checks=("python",)
    )
    assert release.ready is False
    with pytest.raises(SharedContractError, match="mobile"):
        release.require_ready()
    ready = ReleaseEvidence.create(
        revision=revision, required_checks=("python", "mobile"), successful_checks=("python", "mobile", "codeql")
    )
    assert ready.ready is True
    ready.require_ready()


def test_release_contract_rejects_non_exact_revision():
    with pytest.raises(SharedContractError):
        ReleaseEvidence.create(revision="main", required_checks=("python",), successful_checks=("python",))
