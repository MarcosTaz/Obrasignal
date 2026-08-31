"""Failing-before probe for Q090 Company State persistence on the current trust spine.

Acceptance-only. No Q090 runtime promotion and no duplicate Persistence #238 verifier.
"""

from pathlib import Path


def test_company_state_persistence_owner_exists_on_current_spine():
    store = Path("company_state_store.py")
    assert store.exists(), "Q090_PERSISTENCE_MISSING: company_state_store.py absent on current spine"
    text = store.read_text(encoding="utf-8")
    assert "company_state_snapshots" in text
    assert "UNIQUE(account_id" in text or "account_id,state_version" in text.replace(" ", "")


def test_company_state_contract_keeps_unknown_distinct_from_zero():
    domain = Path("company_state.py")
    assert domain.exists(), "Q090_CONTRACT_MISSING: company_state.py absent on current spine"
    text = domain.read_text(encoding="utf-8")
    assert "UNKNOWN" in text
    assert "FACT" in text


def test_q090_remains_prebuild_without_runtime_registration():
    cors = Path("cors_app.py").read_text(encoding="utf-8")
    assert "company_state_api" not in cors
