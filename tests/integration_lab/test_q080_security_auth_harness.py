from pathlib import Path


AUTH_E2E = Path('.github/workflows/authenticated-e2e.yml')
RENDER = Path('render.yaml')


def test_authenticated_e2e_tenant_binding_coexists_with_q080_safe_defaults():
    workflow = AUTH_E2E.read_text(encoding='utf-8')
    render = RENDER.read_text(encoding='utf-8')

    assert "open('/tmp/authenticated_account_id', 'w', encoding='utf-8').write(str(account_id))" in workflow
    assert "assert str(payload.get('account_id')) == expected_account_id" in workflow
    assert "assert str(stats.get('account_id')) == expected_account_id" in workflow
    assert "assert str(workflow.get('account_id')) == expected_account_id" in workflow
    assert "tr '/' '_'" in workflow
    assert "Authenticated API identity verified for account:" not in workflow

    assert 'key: OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1' in render
    assert 'key: OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1' in render
    assert render.count('value: "false"') >= 2
    assert 'OBRASIGNAL_JWKS_URL' not in render


def test_authenticated_e2e_does_not_claim_branch_deployment_identity():
    workflow = AUTH_E2E.read_text(encoding='utf-8')
    # The production E2E harness validates the deployed service; it must not
    # pretend the current PR SHA is deployed merely because its test contract
    # is present in this integration tree.
    assert 'RENDER_GIT_COMMIT' in workflow
    assert 'Confirm deployed backend revision' in workflow
