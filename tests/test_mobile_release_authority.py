from pathlib import Path


LEGACY_AUTOMATIC_EAS = Path(".github/workflows/eas-production.yml")
MOBILE_RELEASE_PREFLIGHT = Path(".github/workflows/mobile-release-preflight.yml")


def test_mobile_production_build_has_single_manual_authority():
    assert not LEGACY_AUTOMATIC_EAS.exists()

    workflow = MOBILE_RELEASE_PREFLIGHT.read_text(encoding="utf-8")
    build_step = workflow.index("- name: Authenticated EAS production build")
    report_step = workflow.index("- name: Upload EAS build report")

    assert "workflow_dispatch:" in workflow
    assert "target_sha:" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow[build_step:report_step]
    assert "Require EAS token for manual release" in workflow
    assert "--profile production" in workflow[build_step:report_step]
    assert "--non-interactive --wait --json" in workflow[build_step:report_step]
    assert "eas-build-report.json" in workflow[report_step:]


def test_manual_production_build_is_exact_current_main_and_reproducible():
    workflow = MOBILE_RELEASE_PREFLIGHT.read_text(encoding="utf-8")

    assert "ref: ${{ github.event_name == 'workflow_dispatch' && inputs.target_sha || github.sha }}" in workflow
    assert 'test "$(git rev-parse HEAD)" = "$RELEASE_TARGET_SHA"' in workflow
    assert 'canonical="$(git rev-parse origin/main)"' in workflow
    assert 'test "$canonical" = "$RELEASE_TARGET_SHA"' in workflow
    assert "eas-cli@21.7.1" in workflow
    assert "eas-cli@latest" not in workflow
    assert "--no-wait" not in workflow
    assert "release-build-evidence.json" in workflow
    assert "build_ids" in workflow
    assert "eas submit" not in workflow.lower()
