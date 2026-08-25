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


def test_production_smoke_does_not_assume_a_main_push_was_deployed():
    workflow = PRODUCTION_SMOKE_WORKFLOW.read_text(encoding="utf-8")

    assert "\n  push:\n" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "target_sha:" in workflow
    assert "Resolve canonical main" in workflow
    target_gate = workflow.index("- name: Resolve verification target without assuming main is deployed")
    backend_gate = workflow.index("- name: Wake and check exact API deployment health")
    protected_probe = workflow.index("- name: Check protected API boundary")
    web_gate = workflow.index("- name: Check exact deployed Web build")
    assert target_gate < backend_gate < protected_probe < web_gate

    assert 'test "$target" = "$canonical"' in workflow
    assert 'intent="RELEASE_VERIFY"' in workflow
    assert 'intent="MONITOR_DEPLOYED"' in workflow
    assert "health.get('build')" in workflow
    assert "TARGET_BUILD=$target" in workflow


def test_production_smoke_requires_one_exact_backend_and_web_target():
    workflow = PRODUCTION_SMOKE_WORKFLOW.read_text(encoding="utf-8")

    assert "health.get('service') == 'obrasignal-api'" in workflow
    assert "health.get('build') == os.environ['TARGET_BUILD']" in workflow
    assert "auth.get('mode') == 'provider'" in workflow
    assert "auth.get('config_present') is True" in workflow
    assert "auth.get('provider_status') in {'uninitialized', 'ready'}" in workflow
    assert 'expected="${TARGET_BUILD:0:7}"' in workflow
    assert 'marker="<meta name=\\"obrasignal-build\\" content=\\"${expected}\\">"' in workflow
    assert 'grep -Fq "$marker" /tmp/web.html' in workflow


def test_production_smoke_persists_drift_and_truthful_release_history_even_on_failure():
    workflow = PRODUCTION_SMOKE_WORKFLOW.read_text(encoding="utf-8")

    assert "id: target" in workflow
    assert "id: backend" in workflow
    assert "id: protected" in workflow
    assert "id: cors" in workflow
    assert "id: web" in workflow
    assert workflow.count("always()") >= 5
    assert "Write bounded production release evidence" in workflow
    assert "Upload production release evidence" in workflow
    assert "'schema_version': 2" in workflow
    assert "'verification': 'VERIFIED' if verified else 'FAILED'" in workflow
    assert "'failure_class': None if verified else 'UNKNOWN'" in workflow
    assert "'release_intent': intent" in workflow
    assert "'canonical_main_sha': canonical" in workflow
    assert "'main_drift': main_drift" in workflow
    assert "'production_alignment': alignment" in workflow
    assert "'rollback': {" in workflow
    assert "'status': 'UNPROVEN'" in workflow
    assert "'target_sha': None" in workflow
    assert "release-proof.json" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "health_is_liveness_not_full_db_worker_dependency_readiness" in workflow
    assert "does_not_prove_authenticated_customer_journey" in workflow
