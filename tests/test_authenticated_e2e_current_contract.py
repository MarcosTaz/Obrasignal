"""Cross-owner regression for production Auth E2E safety and workflow contract truth."""
from pathlib import Path


def test_authenticated_e2e_is_read_only_hardened_and_consumes_nested_workflow_envelope():
    workflow = Path('.github/workflows/authenticated-e2e.yml').read_text(encoding='utf-8')
    provider = Path('api.py').read_text(encoding='utf-8')

    # Release safety: automatic production E2E must remain read-only. Match actual
    # command/function shapes, not the fail-closed self-check's string literals.
    forbidden = []
    for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        forbidden.extend((
            f'-X {method} "$API_URL',
            f"-X {method} '$API_URL",
            f'--request {method} "$API_URL',
            f"--request {method} '$API_URL",
        ))
    forbidden.extend((
        'restore_profile() {',
        'restore_workflow() {',
        'trap restore_profile',
        'trap restore_workflow',
    ))
    assert not [needle for needle in forbidden if needle in workflow]

    # Auth/Supply-Chain owner hardening must survive the Release overlay.
    assert 'actions/checkout@11d5960a326750d5838078e36cf38b85af677262' in workflow
    assert 'persist-credentials: false' in workflow

    # Canonical provider GET is an envelope. The production harness must consume
    # workflow state from that nested envelope, never from the response root.
    assert 'return jsonify({"workflow": workflow, "account_id": identity.account_id' in provider
    assert "workflow_payload.get('workflow')" in workflow
    assert "workflow_payload.get('account_id')" in workflow
    assert "workflow.get('status')" in workflow
    assert "workflow_payload.get('status')" not in workflow


def test_authenticated_e2e_empty_data_is_explicitly_not_full_workflow_proof():
    workflow = Path('.github/workflows/authenticated-e2e.yml').read_text(encoding='utf-8')
    assert 'AUTHENTICATED_DETAIL_WORKFLOW=NOT_RUN_EMPTY_OPPORTUNITY' in workflow
