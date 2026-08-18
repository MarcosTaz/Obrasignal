import json

from company_profile import load_profile, save_profile


def test_profiles_are_isolated_by_account(tmp_path, monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_PROFILE_DIR", str(tmp_path / "profiles"))

    save_profile({"name": "Empresa A", "activity": "metalomecânica"}, account_id="a")
    save_profile({"name": "Empresa B", "activity": "construção"}, account_id="b")

    profile_a = load_profile("a")
    profile_b = load_profile("b")

    assert profile_a["account_id"] == "a"
    assert profile_a["name"] == "Empresa A"
    assert profile_b["account_id"] == "b"
    assert profile_b["name"] == "Empresa B"

    assert (tmp_path / "profiles" / "a.json").exists()
    assert (tmp_path / "profiles" / "b.json").exists()


def test_default_profile_keeps_legacy_path(tmp_path, monkeypatch):
    legacy = tmp_path / "company_profile.json"
    monkeypatch.setenv("OBRASIGNAL_PROFILE", str(legacy))

    saved = save_profile({"name": "Legacy", "activity": "metalomecânica"})
    loaded = load_profile()

    assert saved["account_id"] == "default"
    assert loaded["account_id"] == "default"
    assert loaded["name"] == "Legacy"
    assert legacy.exists()


def test_account_id_is_not_accepted_from_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_PROFILE_DIR", str(tmp_path / "profiles"))

    save_profile({"name": "Safe", "activity": "metalomecânica"}, account_id="../outside")

    expected = tmp_path / "profiles" / ".._outside.json"
    assert expected.exists()
    assert not (tmp_path / "outside.json").exists()
    assert json.loads(expected.read_text(encoding="utf-8"))["account_id"] == "../outside"
