"""Passing-after contract for ordinary Profile edits after partial Radar failure."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "mobile" / "App.js").read_text(encoding="utf-8")
API = (ROOT / "mobile" / "src" / "api.js").read_text(encoding="utf-8")


def test_editor_helper_checks_recovery_before_unwrapping_profile():
    helper = API.split("async function saveProfileForEditor", 1)[1].split("export const api", 1)[0]
    assert "state?.profile_saved===true" in helper
    assert "state?.radar_state==='RECOVERY_REQUIRED'" in helper
    assert "recovery.code='RADAR_RECOVERY_REQUIRED'" in helper
    assert "recovery.responseBody=state" in helper
    assert helper.index("RECOVERY_REQUIRED") < helper.index("return unwrapProfile(state)")


def test_existing_editor_catch_keeps_partial_state_from_becoming_full_success():
    editor = APP.split("const saveProfile=async patch=>", 1)[1].split("const onRefresh=", 1)[0]
    # setProfile/cache/tab/refresh happen only after await api.saveProfile returns.
    # The typed recovery exception therefore exits to the catch before those
    # full-success effects and its truthful message is rendered to the user.
    assert "await api.saveProfile" in editor
    assert editor.index("await api.saveProfile") < editor.index("setProfile(next)")
    assert "setProfileError(e?.responseBody?.error||e?.message" in editor
    assert "setTab('radar')" in editor
    assert "await load({manual:true})" in editor


def test_initial_onboarding_still_consumes_full_state_envelope():
    assert "saveProfileState:async(profile)=>writeWhenReady" in API
    onboarding = (ROOT / "mobile" / "components" / "ProfileOnboarding.js").read_text(encoding="utf-8")
    assert "api.saveProfileState(draft)" in onboarding
    assert "RECOVERY_REQUIRED" in onboarding
