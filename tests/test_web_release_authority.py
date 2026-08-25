from pathlib import Path


WEB_RELEASE = Path(".github/workflows/web-preview.yml")


def test_pages_deployment_requires_explicit_manual_authorization():
    workflow = WEB_RELEASE.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "target_sha:" in workflow
    assert "RELEASE_TARGET_SHA:" in workflow
    assert "cancel-in-progress: false" in workflow

    build_job = workflow.index("\n  build:\n")
    deploy_job = workflow.index("\n  deploy:\n")
    deploy_action = workflow.index("uses: actions/deploy-pages@v4")
    assert build_job < deploy_job < deploy_action

    deploy_section = workflow[deploy_job:]
    assert "if: ${{ github.event_name == 'workflow_dispatch' }}" in deploy_section
    assert "pages: write" in deploy_section
    assert "id-token: write" in deploy_section

    top_permissions = workflow[workflow.index("permissions:"):workflow.index("concurrency:")]
    assert "contents: read" in top_permissions
    assert "pages: write" not in top_permissions
    assert "id-token: write" not in top_permissions


def test_push_main_can_build_but_cannot_deploy_pages():
    workflow = WEB_RELEASE.read_text(encoding="utf-8")

    assert "\n  push:\n" in workflow
    deploy_job = workflow.index("\n  deploy:\n")
    before_deploy = workflow[:deploy_job]
    after_deploy = workflow[deploy_job:]

    assert "actions/deploy-pages@v4" not in before_deploy
    assert "actions/deploy-pages@v4" in after_deploy
    assert "if: ${{ github.event_name == 'workflow_dispatch' }}" in after_deploy


def test_manual_pages_release_is_exact_current_main_and_detects_drift():
    workflow = WEB_RELEASE.read_text(encoding="utf-8")

    assert "ref: ${{ env.RELEASE_TARGET_SHA }}" in workflow
    assert 'test "$(git rev-parse HEAD)" = "$RELEASE_TARGET_SHA"' in workflow
    assert 'canonical="$(git rev-parse origin/main)"' in workflow
    assert 'test "$canonical" = "$RELEASE_TARGET_SHA"' in workflow
    assert "Reconfirm target is current canonical main before deploy" in workflow
    assert "Fail closed on pre-deploy main drift" in workflow
    assert "detect post-deploy drift" in workflow
    assert 'test "$canonical" = "$TARGET_SHA"' in workflow


def test_pages_release_verifies_exact_deployed_web_identity():
    workflow = WEB_RELEASE.read_text(encoding="utf-8")

    assert "Stamp release candidate into page" in workflow
    assert "obrasignal-build" in workflow
    assert 'expected="${TARGET_SHA:0:7}"' in workflow
    assert 'marker="<meta name=\\"obrasignal-build\\" content=\\"${expected}\\">"' in workflow
    assert 'grep -Fq "$marker" /tmp/web.html' in workflow
