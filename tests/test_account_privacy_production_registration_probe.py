from pathlib import Path


CORS_APP = Path('cors_app.py').read_text(encoding='utf-8')
PRIVACY = Path('account_privacy.py').read_text(encoding='utf-8')


def test_account_privacy_owner_routes_exist_but_must_be_registered_in_production():
    assert '@bp.get("/export")' in PRIVACY
    assert '@bp.route("/deletion", methods=["GET", "POST"])' in PRIVACY
    assert 'from account_privacy import bp as ACCOUNT_PRIVACY_BP' in CORS_APP
    assert 'APP.register_blueprint(ACCOUNT_PRIVACY_BP)' in CORS_APP


def test_production_registration_is_idempotent_and_keeps_mobile_api_registration():
    assert 'if "mobile_api" not in APP.blueprints:' in CORS_APP
    assert 'APP.register_blueprint(MOBILE_API_BP)' in CORS_APP
    assert 'if "account_privacy" not in APP.blueprints:' in CORS_APP
