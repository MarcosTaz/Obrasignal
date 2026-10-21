from __future__ import annotations

import copy

import pytest

from web_production_browser_preflight import (
    DEFAULT_PREFLIGHT,
    BrowserPreflightError,
    assert_current_main,
    audit_preflight,
    load_preflight,
    validate_preflight,
)


EXPECTED_MAIN = "66d43f6fd51cf9cea08016dad335aaa04b711a24"


def _preflight():
    return load_preflight(DEFAULT_PREFLIGHT)


def _all_required_pass():
    preflight = copy.deepcopy(_preflight())
    for item in [*preflight["config_requirements"], *preflight["journey_matrix"]]:
        if item.get("required") is True:
            item["result"] = "PASS"
            item.pop("conditional_skip", None)
    return preflight


def _item(preflight, item_id):
    return next(
        item
        for item in [*preflight["config_requirements"], *preflight["journey_matrix"]]
        if item["id"] == item_id
    )


def test_current_preflight_is_truthfully_no_go():
    result = audit_preflight(_preflight())
    assert result.verdict == "NO_GO"
    assert "EXACT_DEPLOYED_BUILD" in result.unknowns
    assert "DETERMINISTIC_CUSTOMER_DATA" in result.unknowns
    assert "TENANT_A_B_ISOLATION" in result.unknowns
    assert "ERROR_DEGRADED_OFFLINE" in result.unknowns


def test_unknown_required_step_fails_closed():
    preflight = _all_required_pass()
    _item(preflight, "SIGNUP_LOGIN")["result"] = "UNKNOWN"
    result = audit_preflight(preflight)
    assert result.verdict == "NO_GO"
    assert result.unknowns == ("SIGNUP_LOGIN",)


def test_fail_required_step_fails_closed():
    preflight = _all_required_pass()
    _item(preflight, "SESSION_RELOAD")["result"] = "FAIL"
    result = audit_preflight(preflight)
    assert result.verdict == "NO_GO"
    assert result.blockers == ("SESSION_RELOAD",)


def test_blocked_external_is_not_go():
    preflight = _all_required_pass()
    _item(preflight, "SUPABASE_REDIRECT")["result"] = "BLOCKED_EXTERNAL"
    result = audit_preflight(preflight)
    assert result.verdict == "NO_GO"
    assert result.unknowns == ("SUPABASE_REDIRECT",)


def test_required_conditional_skip_is_contract_error():
    preflight = _all_required_pass()
    detail = _item(preflight, "DETAIL_SOURCE")
    detail["conditional_skip"] = True
    with pytest.raises(BrowserPreflightError, match="cannot use a conditional skip"):
        validate_preflight(preflight)


def test_saved_watch_remains_non_blocking_current_scope():
    preflight = _all_required_pass()
    saved = _item(preflight, "SAVED_WATCH")
    assert saved["required"] is False
    assert saved["result"] == "NOT_IN_SCOPE"
    result = audit_preflight(preflight)
    assert result.verdict == "GO"


def test_saved_watch_cannot_silently_become_release_requirement():
    preflight = _all_required_pass()
    saved = _item(preflight, "SAVED_WATCH")
    saved["required"] = True
    saved["result"] = "PASS"
    with pytest.raises(BrowserPreflightError, match="SAVED_WATCH must remain"):
        validate_preflight(preflight)


def test_secret_bearing_evidence_fields_are_rejected():
    preflight = copy.deepcopy(_preflight())
    preflight["captured_evidence"] = {"access_token": "redacted-is-still-wrong-field"}
    with pytest.raises(BrowserPreflightError, match="secret-bearing field"):
        validate_preflight(preflight)


def test_token_like_material_is_rejected():
    preflight = copy.deepcopy(_preflight())
    _item(preflight, "SIGNUP_LOGIN")["evidence"] = [
        "Bearer eyJabc.def.ghi"
    ]
    with pytest.raises(BrowserPreflightError, match="token-like material"):
        validate_preflight(preflight)


def test_go_requires_every_required_row_to_pass():
    result = audit_preflight(_all_required_pass())
    assert result.verdict == "GO"
    assert result.blockers == ()
    assert result.unknowns == ()


def test_main_drift_invalidates_browser_preflight():
    assert_current_main(_preflight(), EXPECTED_MAIN)
    with pytest.raises(BrowserPreflightError, match="preflight is stale"):
        assert_current_main(_preflight(), "f" * 40)
