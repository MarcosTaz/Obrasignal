"""Customer Value failing-before: profile editor must preserve partial Radar state.

DO NOT MERGE / NOT CLIENT OWNER REPAIR / NOT CANONICAL.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_existing_profile_editor_cannot_treat_recovery_required_as_complete_save():
    app = (ROOT / "mobile" / "App.js").read_text(encoding="utf-8")

    # Initial onboarding now preserves the full profile POST envelope, but the
    # existing profile editor still uses api.saveProfile(), which unwraps every
    # successful 2xx response to the profile object. A backend 202 therefore
    # loses RECOVERY_REQUIRED and can navigate to Radar as if recalculation had
    # completed.
    assert "api.saveProfileState({...profile,...patch})" in app
    assert "radar_state==='RECOVERY_REQUIRED'" in app

    handler = app.split("const saveProfile=async patch=>", 1)[1].split("const onRefresh=", 1)[0]
    recovery = handler.split("radar_state==='RECOVERY_REQUIRED'", 1)[1].split("setTab('radar')", 1)[0]
    assert "setProfileError" in recovery
    assert "Radar" in recovery
    assert "return" in recovery
