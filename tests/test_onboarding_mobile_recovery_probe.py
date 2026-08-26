"""Customer Value failing-before: Mobile must not erase explicit onboarding recovery state.

DO NOT MERGE / NOT CLIENT OWNER REPAIR / NOT CANONICAL.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_save_profile_preserves_explicit_radar_recovery_state():
    api_source = (ROOT / "mobile" / "src" / "api.js").read_text(encoding="utf-8")
    onboarding_source = (ROOT / "mobile" / "components" / "ProfileOnboarding.js").read_text(encoding="utf-8")

    # #542 can expose a truthful 202 envelope after durable profile save:
    # {profile_saved:true, profile:{...}, radar_state:'RECOVERY_REQUIRED'}.
    # The client must preserve and branch on that state instead of unwrapping the
    # profile and treating every 2xx as complete onboarding success.
    assert "RECOVERY_REQUIRED" in api_source
    assert "radar_state" in api_source
    assert "RECOVERY_REQUIRED" in onboarding_source
    assert "radar_state" in onboarding_source
