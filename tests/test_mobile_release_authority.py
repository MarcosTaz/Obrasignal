from pathlib import Path


LEGACY_AUTOMATIC_EAS = Path(".github/workflows/eas-production.yml")
MOBILE_RELEASE_PREFLIGHT = Path(".github/workflows/mobile-release-preflight.yml")


def test_mobile_production_build_has_single_manual_authority():
    assert not LEGACY_AUTOMATIC_EAS.exists()

    workflow = MOBILE_RELEASE_PREFLIGHT.read_text(encoding="utf-8")
    build_step = workflow.index("- name: Authenticated EAS production build")
    report_step = workflow.index("- name: Upload EAS build report")

    assert "workflow_dispatch:" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow[build_step:report_step]
    assert "Require EAS token for manual release" in workflow
    assert "--profile production" in workflow[build_step:report_step]
    assert "--non-interactive --wait --json" in workflow[build_step:report_step]
    assert "eas-build-report.json" in workflow[report_step:]
