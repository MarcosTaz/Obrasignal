import json
import sqlite3

from company_profile import load_profile, save_profile


def test_profiles_are_isolated_by_account(tmp_path, monkeypatch):
    db_path = tmp_path / "profiles.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))

    save_profile({"name": "Empresa A", "activity": "metalomecânica"}, account_id="a")
    save_profile({"name": "Empresa B", "activity": "construção"}, account_id="b")

    profile_a = load_profile("a")
    profile_b = load_profile("b")

    assert profile_a["account_id"] == "a"
    assert profile_a["name"] == "Empresa A"
    assert profile_b["account_id"] == "b"
    assert profile_b["name"] == "Empresa B"

    with sqlite3.connect(db_path) as conn:
        accounts = {
            row[0]
            for row in conn.execute("SELECT account_id FROM company_profiles")
        }
    assert accounts == {"a", "b"}


def test_default_profile_uses_durable_database_not_legacy_path(tmp_path, monkeypatch):
    legacy = tmp_path / "company_profile.json"
    db_path = tmp_path / "profiles.db"
    monkeypatch.setenv("OBRASIGNAL_PROFILE", str(legacy))
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))

    saved = save_profile({"name": "Legacy", "activity": "metalomecânica"})
    loaded = load_profile()

    assert saved["account_id"] == "default"
    assert loaded["account_id"] == "default"
    assert loaded["name"] == "Legacy"
    assert not legacy.exists()
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT profile_json FROM company_profiles WHERE account_id='default'"
        ).fetchone()
    assert json.loads(row[0])["name"] == "Legacy"


def test_account_id_cannot_escape_database_storage_via_path_traversal(tmp_path, monkeypatch):
    db_path = tmp_path / "profiles.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))

    save_profile({"name": "Safe", "activity": "metalomecânica"}, account_id="../outside")

    assert not (tmp_path / "outside.json").exists()
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT profile_json FROM company_profiles WHERE account_id=?",
            ("../outside",),
        ).fetchone()
    assert json.loads(row[0])["account_id"] == "../outside"
