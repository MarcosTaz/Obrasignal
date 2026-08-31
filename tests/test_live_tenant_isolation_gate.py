from pathlib import Path


def test_live_tenant_workflow_requires_two_distinct_identity_sources():
    workflow = Path('.github/workflows/tenant-isolation-live.yml').read_text(encoding='utf-8')
    assert 'E2E_EMAIL_B: ${{ secrets.E2E_EMAIL_B }}' in workflow
    assert 'E2E_PASSWORD_B: ${{ secrets.E2E_PASSWORD_B }}' in workflow
    assert 'TARGET_BUILD: ${{ github.sha }}' in workflow
    assert 'python scripts/provision_ephemeral_tenant.py' in workflow
    assert 'python scripts/live_tenant_isolation_runner.py' in workflow

    runner = Path('scripts/live_tenant_isolation_runner.py').read_text(encoding='utf-8')
    assert 'import live_tenant_isolation_e2e as probe' in runner
    assert 'E2E_ACCESS_TOKEN_B' in runner
    assert 'E2E_USER_ID_B' in runner
    assert 'probe.sign_in = _sign_in' in runner
    assert 'probe.main()' in runner

    provisioner = Path('scripts/provision_ephemeral_tenant.py').read_text(encoding='utf-8')
    assert '/auth/v1/signup' in provisioner
    assert 'req.add_header("apikey", key)' in provisioner
    assert 'E2E_ACCESS_TOKEN_B=' in provisioner
    assert 'E2E_USER_ID_B=' in provisioner


def test_live_tenant_probe_attacks_forged_account_claims_and_cross_profile_state():
    source = Path('scripts/live_tenant_isolation_e2e.py').read_text(encoding='utf-8')
    assert 'X-Account-Id' in source
    assert 'X-Tenant-Id' in source
    assert "query['account_id'] = claimed_account" in source
    assert 'CROSS_TENANT_LEAK saw other tenant profile marker' in source
    assert 'CROSS_TENANT_LEAK: tenant B saw tenant A workflow note' in source
    assert "a['id'] != b['id']" in source


def test_live_tenant_probe_is_fail_closed_when_proof_material_is_missing():
    source = Path('scripts/live_tenant_isolation_e2e.py').read_text(encoding='utf-8')
    assert 'OWNER_ONLY_BLOCKER: configure E2E_EMAIL_B and E2E_PASSWORD_B' in source
    assert 'CUSTOMER_READY_BLOCKER: no production opportunity was accessible to both dedicated tenants' in source
    assert 'production never served exact target build' in source
