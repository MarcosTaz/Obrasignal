from pathlib import Path


def test_profile_editor_surfaces_server_validation_detail_instead_of_generic_invalid_profile():
    api_source = Path("mobile/src/api.js").read_text(encoding="utf-8")
    app_source = Path("mobile/App.js").read_text(encoding="utf-8")

    assert "actionableProfileValidationError" in api_source
    assert "error?.responseBody?.detail?.errors" in api_source
    assert "error?.responseBody?.error!=='invalid_profile'" in api_source
    assert "messages.join(' ')" in api_source

    # Existing editor surfaces already prefer responseBody.error, so the API
    # adapter must replace only the client-facing error text while preserving the
    # server response envelope and validation authority.
    assert "setProfileError(e?.responseBody?.error||e?.message" in app_source
    assert "error.responseBody={...error.responseBody,error:message}" in api_source


def test_profile_editor_validation_adapter_does_not_reinterpret_other_failures():
    api_source = Path("mobile/src/api.js").read_text(encoding="utf-8")

    assert "if(error?.responseBody?.error!=='invalid_profile'||!Array.isArray(details))return error;" in api_source
    assert "if(!messages.length)return error;" in api_source
