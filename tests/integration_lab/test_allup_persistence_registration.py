from pathlib import Path

from storage_contract import KNOWN_TABLE_OWNERS, declared_persistent_tables


def test_allup_persistent_tables_are_registered():
    source = Path("company_state_store.py").read_text(encoding="utf-8")
    declared = declared_persistent_tables(source)
    missing = sorted(declared - set(KNOWN_TABLE_OWNERS))
    assert not missing, f"unregistered persistent tables in all-up integration: {missing}"
