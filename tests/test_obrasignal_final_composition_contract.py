from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_customer_privacy_stays_outside_billing_gate():
    auth = text("mobile/components/AuthGate.js")
    assert "AccountPrivacyControls" in auth
    assert "PasswordRecoveryScreen" in auth
    assert auth.index("<AccountPrivacyControls") < auth.index("<BillingGate")
    assert "WebSessionBar" in auth
    assert "WebTranslator" in auth


def test_mobile_client_keeps_write_refresh_privacy_pagination_and_watchlist():
    api = text("mobile/src/api.js")
    assert "response.status===401 && !skipAuth && authRefreshes===0" in api
    assert "method==='GET'" not in api
    assert "accountExport" in api and "requestAccountDeletion" in api
    assert "offset:String(offset)" in api
    assert "savedOpportunities" in api and "saveOpportunity" in api and "unsaveOpportunity" in api


def test_billing_never_uses_provider_entitlement_as_product_access_authority():
    gate = text("mobile/components/BillingGate.js")
    assert "authority: 'loading'" in gate
    assert "pro: server.plan === 'pro'" in gate
    assert "SERVER_PLANS" in gate
    assert "hasProEntitlement(info)" not in gate
    assert "server?.plan ||" not in gate
    assert "server ainda não confirmou" in gate


def test_company_truth_modules_and_production_registration_exist():
    for path in (
        "account_privacy.py",
        "account_privacy_composition.py",
        "account_privacy_integrity.py",
        "company_state.py",
        "company_state_store.py",
        "notification_dispatch_guard.py",
        "notification_privacy_lifecycle.py",
        "opportunity_watchlist_api.py",
        "pursuit_workspace.py",
        "storage_contract.py",
        "storage_recovery.py",
    ):
        assert (ROOT / path).is_file(), path
    cors = text("cors_app.py")
    privacy = text("account_privacy.py")
    watch = text("opportunity_watchlist_api.py")
    assert "ACCOUNT_PRIVACY_BP" in cors and '"account_privacy" not in APP.blueprints' in cors
    assert "register_watchlist_api()" in watch
    assert "account_privacy" in privacy


def test_release_workflow_is_manual_exact_sha_and_waits_for_evidence():
    workflow = text(".github/workflows/eas-production.yml")
    assert "workflow_dispatch:" in workflow
    assert "target_sha:" in workflow
    assert "git rev-parse origin/main" in workflow
    assert "eas-cli@21.7.1" in workflow
    assert "--wait" in workflow
    assert "release-build-evidence.json" in workflow
    assert "push:" not in workflow
    assert "--no-wait" not in workflow


def test_commercial_web_and_europe_market_surface_remain_present():
    web = text("mobile/App.web.js")
    markets = text("mobile/src/markets.js")
    assert "EUROPE_MARKETS" in web
    assert "EUROPE_MARKETS" in markets
    assert markets.count("code:") >= 30


def test_backend_radar_contract_is_paginated_account_bounded_and_production_wired():
    radar = text("account_scoped_radar.py")
    cors = text("cors_app.py")
    assert 'request.args.get("offset"' in radar
    assert '"page": page' in radar
    assert "FROM opportunity_decisions d" in radar
    assert "WHERE d.account_id=?" in radar
    assert "d.rule_version=?" in radar
    assert "d.profile_fingerprint=?" in radar
    assert 'request.args.get("market") or ""' in radar
    assert 'request.path == "/api/v1/opportunities"' in cors
    assert "handle_account_scoped_opportunities()" in cors
