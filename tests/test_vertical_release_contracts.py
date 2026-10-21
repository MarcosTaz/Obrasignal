import pytest

from factory_cloud.shared_contracts import SharedContractError
from vertical_apps.aviation_recovery.release import release_ready as aviation_release_ready
from vertical_apps.contractcredit.release import release_ready as contractcredit_release_ready


def test_two_vertical_apps_use_same_exact_sha_release_contract():
    revision = "b" * 40
    assert aviation_release_ready(revision=revision, successful_checks=("python", "mobile")) is True
    assert contractcredit_release_ready(revision=revision, successful_checks=("python", "mobile", "codeql")) is True


def test_vertical_release_contracts_fail_closed_on_missing_check():
    revision = "b" * 40
    with pytest.raises(SharedContractError, match="mobile"):
        aviation_release_ready(revision=revision, successful_checks=("python",))
    with pytest.raises(SharedContractError, match="mobile"):
        contractcredit_release_ready(revision=revision, successful_checks=("python",))
