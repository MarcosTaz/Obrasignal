from pathlib import Path


PRODUCTION_BUILD = Path(".github/workflows/eas-production.yml")
MOBILE_PREFLIGHT = Path(".github/workflows/mobile-release-preflight.yml")


def test_mobile_preflight_never_creates_production_artifacts():
    workflow = MOBILE_PREFLIGHT.read_text(encoding="utf-8")

    assert "\n  push:\n" in workflow
    assert "eas-cli@" not in workflow
    assert "eas build" not in workflow
    assert "Authenticated EAS production build" not in workflow
    assert "EXPO_TOKEN" not in workflow


def test_production_build_requires_explicit_exact_current_main_sha():
    workflow = PRODUCTION_BUILD.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "\n  push:\n" not in workflow
    assert "target_sha:" in workflow
    assert "ref: ${{ inputs.target_sha }}" in workflow
    assert 'test "$resolved" = "$TARGET_SHA"' in workflow
    assert 'canonical="$(git rev-parse origin/main)"' in workflow
    assert 'test "$canonical" = "$TARGET_SHA"' in workflow
    assert "EXPO_TOKEN: ${{ secrets.EXPO_TOKEN }}" in workflow


def test_production_build_is_reproducible_bounded_and_evidence_bearing():
    workflow = PRODUCTION_BUILD.read_text(encoding="utf-8")

    assert "eas-cli@21.7.1" in workflow
    assert "--wait" in workflow
    assert "--json > eas-build.json" in workflow
    assert "--no-wait" not in workflow
    assert "release-build-evidence.json" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "eas submit" not in workflow.lower()
