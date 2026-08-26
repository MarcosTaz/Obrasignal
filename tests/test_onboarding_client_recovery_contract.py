"""Passing-after contract for the Mobile side of partial onboarding recovery."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_preserves_backend_recovery_envelope_and_does_not_complete_early():
    api_source = (ROOT / "mobile" / "src" / "api.js").read_text(encoding="utf-8")
    onboarding = (ROOT / "mobile" / "components" / "ProfileOnboarding.js").read_text(encoding="utf-8")

    # The ordinary profile editor may continue consuming the unwrapped profile,
    # but initial onboarding must retain the material server state envelope.
    assert "saveProfileState:async(profile)=>writeWhenReady('/profile'" in api_source
    assert "api.saveProfileState(draft)" in onboarding

    # Backend `RECOVERY_REQUIRED` must remain visible and must not flow through
    # the normal completion callback. The return is the fail-closed boundary.
    branch = "if(result?.radar_state==='RECOVERY_REQUIRED')"
    assert branch in onboarding
    recovery_block = onboarding.split(branch, 1)[1].split("setRecoveryNeeded(false)", 1)[0]
    assert "setRecoveryNeeded(true)" in recovery_block
    assert "perfil ficou guardado" in recovery_block
    assert "Radar ainda não foi actualizado" in recovery_block
    assert "return" in recovery_block
    assert "onComplete(" not in recovery_block

    # Only the non-recovery path may complete onboarding and it must prefer the
    # authoritative server profile rather than the local draft.
    assert "setRecoveryNeeded(false);onComplete(result?.profile||draft)" in onboarding
    assert "recoveryNeeded?'Concluir actualização do Radar':'Criar o meu Radar'" in onboarding
