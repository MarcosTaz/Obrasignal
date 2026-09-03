from pathlib import Path


AUTHENTICATED_WORKFLOW = Path(".github/workflows/authenticated-e2e.yml")
PRODUCTION_SMOKE_WORKFLOW = Path(".github/workflows/production-smoke.yml")


def test_authenticated_e2e_waits_for_exact_deployment_before_identity_requests():
    workflow = AUTHENTICATED_WORKFLOW.read_text(encoding="utf-8")

    deployment_gate = workflow.index("- name: Wait for exact production build")
    contract_probe = workflow.index("- name: Verify authenticated production contract")
    unauthenticated_probe = workflow.index('unauth_status="$(curl', contract_probe)
    authenticated_profile_probe = workflow.index('"$API_URL/profile" > /tmp/profile.json', contract_probe)

    assert deployment_gate < contract_probe < unauthenticated_probe < authenticated_profile_probe
    assert "TARGET_BUILD: ${{ github.sha }}" in workflow
    assert "health.get('service') == 'obrasignal-api'" in workflow
    assert "health.get('build') == os.environ['TARGET_BUILD']" in workflow
    assert '-X POST "$API_URL/profile"' not in workflow


def test_production_smoke_requires_exact_deployed_revision_and_ready_auth_runtime():
    workflow = PRODUCTION_SMOKE_WORKFLOW.read_text(encoding="utf-8")

    deployment_gate = workflow.index("- name: Wake and check exact API deployment health")
    protected_probe = workflow.index("- name: Check protected API boundary")

    assert deployment_gate < protected_probe
    assert "TARGET_BUILD: ${{ github.sha }}" in workflow
    assert "health.get('service') == 'obrasignal-api'" in workflow
    assert "health.get('build') == os.environ['TARGET_BUILD']" in workflow
    assert "auth.get('mode') == 'provider'" in workflow
    assert "auth.get('config_present') is True" in workflow
    assert "auth.get('provider_status') == 'ready'" in workflow
    assert "runtime.get('auth_warm_status') == 'ready'" in workflow
    assert "runtime.get('preflight_first') is True" in workflow
