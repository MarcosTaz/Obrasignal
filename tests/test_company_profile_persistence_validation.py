import pytest

from company_profile import save_profile


def test_invalid_profile_is_rejected_before_persistence(monkeypatch, tmp_path):
    profile_path = tmp_path / "profile.json"
    monkeypatch.setenv("OBRASIGNAL_PROFILE", str(profile_path))

    with pytest.raises(ValueError) as excinfo:
        save_profile({
            "countries": ["PT"],
            "min_value": 1000000,
            "max_value": 100000,
        })

    error = excinfo.value.args[0]
    assert error["code"] == "INVALID_COMPANY_PROFILE"
    assert "min_value: não pode ser superior a max_value." in error["errors"]
    assert not profile_path.exists()
