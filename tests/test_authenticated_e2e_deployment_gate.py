from pathlib import Path


AUTHENTICATED_WORKFLOW = Path(".github/workflows/authenticated-e2e.yml")
PRODUCTION_SMOKE_WORKFLOW = Path(".github/workflows/production-smoke.yml")


def test_authenticated_e2e_waits_for_exact_deployment_before_identity_requests():
    workflow = AUTHENTICATED_WORKFLOW.read_text(encoding="utf-8")

    deployment_gate = workflow.index("- name: Wait for target production deployment")
    unauthenticated_probe = workflow.index("- name: Verify unauthenticated boundary")
    authenticated_probe = workflow.index("- name: Verify authenticated API identity")

    assert deployment_gate < unauthenticated_probe < authenticated_probe
    assert "TARGET_BUILD: ${{ github.sha }}" in workflow
    assert "health.get('service') == 'obrasignal-api'" in workflow
    assert "health.get('build') == os.environ['TARGET_BUILD']" in workflow


def test_production_smoke_requires_exact_deployed_revision():
    workflow = PRODUCTION_SMOKE_WORKFLOW.read_text(encoding="utf-8")

    deployment_gate = workflow.index("- name: Wake and check exact API deployment health")
    protected_probe = workflow.index("- name: Check protected API boundary")

    assert deployment_gate < protected_probe
    assert "TARGET_BUILD: ${{ github.sha }}" in workflow
    assert "health.get('service') == 'obrasignal-api'" in workflow
    assert "health.get('build') == os.environ['TARGET_BUILD']" in workflow
