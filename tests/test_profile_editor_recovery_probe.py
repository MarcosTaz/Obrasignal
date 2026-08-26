"""Customer Value failing-before: existing Profile editor loses partial-state truth.

DO NOT MERGE. This probe is intentionally RED until the editor preserves the
same durable-profile / Radar-recovery distinction already proven for initial
onboarding.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "mobile" / "App.js").read_text(encoding="utf-8")
API = (ROOT / "mobile" / "src" / "api.js").read_text(encoding="utf-8")


def test_profile_editor_does_not_unwrap_away_recovery_required_state():
    # The initial onboarding path already consumes saveProfileState(), but the
    # ordinary Profile editor still calls saveProfile(), whose unwrapProfile()
    # discards radar_state/profile_saved from an HTTP 202 partial-success reply.
    assert "const next=await api.saveProfileState({...profile,...patch})" in APP
    assert "radar_state==='RECOVERY_REQUIRED'" in APP


def test_profile_editor_cannot_complete_as_if_radar_were_current_on_partial_success():
    # A durable profile save followed by Radar failure must keep the editor in a
    # recovery state. It must not cache the profile, switch to Radar, and run a
    # normal refresh as if the save/recalculation transaction were fully green.
    editor = APP.split("const saveProfile=async patch=>", 1)[1].split("const onRefresh=", 1)[0]
    assert "saveProfileState" in editor
    assert "RECOVERY_REQUIRED" in editor
    assert "setProfileError" in editor


def test_legacy_profile_helper_is_not_used_by_customer_edit_surfaces_that_need_state():
    # Keep the convenience unwrap helper available only for callers that truly
    # need a profile object; state-sensitive edits must consume the envelope.
    assert "saveProfile:async(profile)=>unwrapProfile" in API
    assert "saveProfileState:async(profile)=>writeWhenReady" in API
    editor = APP.split("const saveProfile=async patch=>", 1)[1].split("const onRefresh=", 1)[0]
    assert "api.saveProfile(" not in editor
